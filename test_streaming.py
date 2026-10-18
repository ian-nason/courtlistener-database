import bz2,hashlib,io,pathlib,tempfile,unittest
from unittest.mock import patch
import duckdb
import build_database as b
from stream_csv import records,chunks

class RecordTests(unittest.TestCase):
    def test_backslash_quotes_multiline_and_record_boundaries(self):
        content=b'"1","a\\"b\nsecond line\\\\tail"\n"2","done"\n'
        self.assertEqual(list(records(io.BytesIO(content))),[b'"1","a\\"b\nsecond line\\\\tail"\n',b'"2","done"\n'])
    def test_double_quote_legacy_dialect(self):
        content=b'"1","a""b\nsecond line"\n"2","done"\n'
        self.assertEqual(len(list(records(io.BytesIO(content),escape='"'))),2)
    def test_record_and_batch_limits(self):
        with self.assertRaisesRegex(ValueError,'exceeds'):list(records(io.BytesIO(b'"'+b'x'*101+b'"\n'),max_record_bytes=100))
        with self.assertRaisesRegex(ValueError,'batch byte'):list(chunks(io.BytesIO(b'12345\n'),header=b'id\n',max_bytes=8))
        parts=list(chunks(io.BytesIO(b'1\n2\n3\n'),header=b'id\n',max_rows=2))
        self.assertEqual(parts,[(b'id\n1\n2\n',2),(b'id\n3\n',1)])
    def test_unterminated_quote_fails(self):
        with self.assertRaisesRegex(ValueError,'Unterminated'):list(records(io.BytesIO(b'"one\nunfinished')))

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.old=(b.RAW,b.TMP,b.MANIFEST,b.KINDS,b.LOAD_AUDIT)
        b.RAW=self.root;b.TMP=self.root/'chunks';b.MANIFEST={};b.KINDS={'fixture':('fixture','fixture')};b.LOAD_AUDIT={}
        self.con=duckdb.connect(config={'memory_limit':'64MB','threads':'1','max_temp_directory_size':'0B'})
    def tearDown(self):
        self.con.close();b.RAW,b.TMP,b.MANIFEST,b.KINDS,b.LOAD_AUDIT=self.old;self.tmp.cleanup()
    def source(self,content,date='2026-09-30'):
        path=self.root/'fixture.csv.bz2';path.write_bytes(bz2.compress(content))
        b.MANIFEST={'fixture':{'file':path.name,'size':path.stat().st_size,'date':date,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
        return path
    def test_lossless_native_field_parse_and_types(self):
        self.source(b'id,note,valid,day\n"1","a\\"b\nsecond line\\\\tail","t","2026-09-30"\n"2","","f",\n')
        n=b.load(self.con,'fixture',{'fixture':[('id','integer'),('note','text'),('valid','boolean'),('day','date')]})
        self.assertEqual(n,2);rows=self.con.execute('SELECT * FROM fixture ORDER BY id').fetchall()
        self.assertEqual(rows[0][:3],(1,'a"b\nsecond line\\tail',True));self.assertEqual(str(rows[0][3]),'2026-09-30');self.assertEqual(rows[1],(2,None,False,None))
        self.assertEqual(b.LOAD_AUDIT['fixture']['source_records'],2);self.assertEqual(list(b.TMP.iterdir()),[])
    def test_legacy_double_quotes(self):
        self.source(b'id,note\n"1","a""b\nline"\n',date='2024-05-06');b.load(self.con,'fixture',{'fixture':[('id','integer'),('note','text')]})
        self.assertEqual(self.con.execute('SELECT note FROM fixture').fetchone()[0],'a"b\nline')
    def test_bad_typed_values_fail_before_insert(self):
        self.source(b'id,valid,day\n"1.5","yes","2026"\n')
        with self.assertRaisesRegex(ValueError,'invalid typed values'):b.load(self.con,'fixture',{'fixture':[('id','integer'),('valid','boolean'),('day','date')]})
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM fixture').fetchone()[0],0);self.assertFalse(b.LOAD_AUDIT);self.assertEqual(list(b.TMP.iterdir()),[])
    def test_schema_mismatch_fails(self):
        self.source(b'id,extra\n1,x\n')
        with self.assertRaisesRegex(ValueError,'column mismatch'):b.load(self.con,'fixture',{'fixture':[('id','integer')]})
    def test_hash_mismatch_fails(self):
        self.source(b'id\n1\n');b.MANIFEST['fixture']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'checksum'):b.load(self.con,'fixture',{'fixture':[('id','integer')]})
    def test_truncated_compression_fails_without_audit(self):
        path=self.source(b'id\n1\n2\n');path.write_bytes(path.read_bytes()[:-10]);b.MANIFEST['fixture'].update(size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises((EOFError,OSError)):b.load(self.con,'fixture',{'fixture':[('id','integer')]})
        self.assertFalse(b.LOAD_AUDIT)
    def test_retired_empty_oral_field_and_legacy_order_preserved(self):
        header=[c for c in b.LEGACY_ORAL_COLUMNS if c!='stt_google_response']+['stt_transcript','stt_source']
        self.source((','.join(header)+'\n'+','.join('1' if c=='id' else 'new transcript' if c=='stt_transcript' else '' for c in header)+'\n').encode())
        b.MANIFEST={'oral-arguments':b.MANIFEST['fixture']};b.KINDS={'oral-arguments':('oral_arguments','fixture')}
        schema={'fixture':[(c,'integer' if c=='id' else 'text') for c in header]}
        self.assertEqual(b.load(self.con,'oral-arguments',schema),1)
        columns=[x[0] for x in self.con.execute('DESCRIBE oral_arguments').fetchall()]
        self.assertEqual(columns,b.LEGACY_ORAL_COLUMNS+['stt_transcript','stt_source'])
        self.assertEqual(self.con.execute('SELECT stt_google_response,stt_transcript FROM oral_arguments').fetchone(),(None,'new transcript'))
    def test_only_documented_schema_omission_allowed(self):
        self.source(b'id\n1\n');b.MANIFEST={'originating-court-information':b.MANIFEST['fixture']};b.KINDS={'originating-court-information':('fixture','fixture')}
        self.assertEqual(b.load(self.con,'originating-court-information',{'fixture':[('id','integer'),('date_rehearing_denied','date')]}),1)
    def test_native_storage_row_group_limit(self):
        path=self.root/'small-groups.duckdb'
        self.con.execute("ATTACH '"+str(path)+"' AS small (ROW_GROUP_SIZE 2048)")
        self.con.execute("CREATE TABLE small.fixture AS SELECT i,repeat(md5(i::VARCHAR),4) AS payload FROM range(5000) t(i)")
        self.con.execute('CHECKPOINT small')
        groups=self.con.execute("SELECT row_group_id,MAX(count) FROM pragma_storage_info('small.fixture') GROUP BY 1 ORDER BY 1").fetchall()
        self.assertEqual([n for _,n in groups],[2048,2048,904])
    def test_reopen_checkpoint_preserves_small_groups(self):
        path=self.root/'reopen.duckdb'
        self.con.execute("ATTACH '"+str(path)+"' AS reopen (ROW_GROUP_SIZE 2048)")
        self.con.execute("CREATE TABLE reopen.payload AS SELECT i,repeat(md5(i::VARCHAR),8) AS text FROM range(10000) t(i)")
        self.con.execute('CHECKPOINT reopen');self.con.execute('DETACH reopen')
        self.con.execute("ATTACH '"+str(path)+"' AS reopen (ROW_GROUP_SIZE 2048)")
        self.con.execute('CREATE TABLE reopen.metadata AS SELECT 1 AS version')
        self.con.execute('CHECKPOINT reopen')
        groups=self.con.execute("SELECT row_group_id,MAX(count) FROM pragma_storage_info('reopen.payload') GROUP BY 1 ORDER BY 1").fetchall()
        self.assertEqual([n for _,n in groups],[2048,2048,2048,2048,1808])
    def test_multiple_committed_batches_and_counts(self):
        self.source(b'id\n1\n2\n3\n4\n5\n');real=b.chunks
        with patch.object(b,'chunks',side_effect=lambda source,**kw:real(source,max_rows=2,**kw)):
            self.assertEqual(b.load(self.con,'fixture',{'fixture':[('id','integer')]}),5)
        self.assertEqual(b.LOAD_AUDIT['fixture']['batches'],3)

if __name__=='__main__':unittest.main()
