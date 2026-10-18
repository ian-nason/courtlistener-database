import copy,json,pathlib,tempfile,unittest,sys
from types import SimpleNamespace
from unittest.mock import Mock,patch
import duckdb,yaml
import publish_checked as p

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.db=self.root/'fixture.duckdb';self.dictionary=self.root/'DICTIONARY.md';self.dictionary.write_text('stt_transcript')
        self.receipt=self.root/'receipt.json';self.provenance=self.root/'provenance.json';self.parent='a'*40;self.commit='b'*40
        self.spec={'repo':p.EXPECTED_REPO,'file':p.EXPECTED_FILE,'alias':'cl','pretty_name':'Fixture','intro':'Fixture data','license':'other','license_name':'public-domain','license_link':'https://www.courtlistener.com/help/api/bulk-data/','quick_start_sql':'SELECT id FROM cl.judges LIMIT 1'}
        (self.root/'card.yaml').write_text(yaml.safe_dump(self.spec))
        con=duckdb.connect(str(self.db),config=p.CONFIG)
        con.execute('CREATE TABLE judges AS SELECT 1::INTEGER AS id,2::INTEGER AS fjc_id')
        con.execute('CREATE TABLE financial_disclosures AS SELECT 2022::INTEGER AS year')
        con.execute("CREATE TABLE _metadata(table_name VARCHAR,description VARCHAR,row_count BIGINT,column_count INTEGER,license VARCHAR)")
        schemas={}
        for name in ['judges','financial_disclosures']:
            cols=[list(x[:2]) for x in con.execute('DESCRIBE '+name).fetchall()];schemas[name]={'columns':cols,'legacy_columns':len(cols),'new_columns':[]}
            con.execute('INSERT INTO _metadata VALUES (?,?,?,?,?)',[name,'Fixture',1,len(cols),'Public Domain Mark / public records (CourtListener bulk data)'])
        con.close()
        self.report={'status':'validated','sha256':p.checksum(self.db),'bytes':self.db.stat().st_size,'counts':{x:{'new':1} for x in schemas},'schemas':schemas,'queries':{'judges':[1,1]},'dates':{'disclosure_years':[2022,2022]}}
        self.doc={'source_snapshot':'2026-09-30','dictionary_sha256':p.checksum(self.dictionary),'validation':self.report,'previous_artifact':{'commit':self.parent}};self.save()
        self.api=Mock();self.api.repo_info.return_value=SimpleNamespace(sha=self.parent);self.api.get_paths_info.return_value=[SimpleNamespace(size=4,lfs=SimpleNamespace(sha256='c'*64))];self.api.create_commit.return_value=SimpleNamespace(oid=self.commit,commit_url='https://example.invalid/commit/'+self.commit)
    def save(self):self.provenance.write_text(json.dumps(self.doc))
    def tearDown(self):self.tmp.cleanup()
    def run_main(self,*extra):
        args=['publish_checked.py','--db',str(self.db),'--dictionary',str(self.dictionary),'--provenance',str(self.provenance),'--receipt',str(self.receipt),'--expected-parent',self.parent,*extra]
        with patch.object(sys,'argv',args),patch.object(p,'__file__',str(self.root/'publish_checked.py')),patch.object(p,'HfApi',return_value=self.api):p.main()
    def test_flat_and_nested_reports(self):
        self.assertEqual(p.validation_report(self.doc),self.report);self.assertEqual(p.validation_report(self.report),self.report)
    def test_invalid_report_fails(self):
        for key,value in [('status','failed'),('counts',{'bad;sql':{'new':1}}),('schemas',{})]:
            bad=copy.deepcopy(self.report);bad[key]=value
            with self.assertRaises(ValueError):p.validation_report(bad)
    def test_dry_run_never_uploads(self):
        self.run_main('--dry-run');self.api.create_commit.assert_not_called();self.assertFalse(self.receipt.exists())
        card=self.receipt.with_suffix('.README.md').read_text();self.assertIn('install.packages("datapond")',card);self.assertIn('2 rows across 2 tables',card)
    def test_changed_head_blocks_upload(self):
        self.api.repo_info.return_value.sha='d'*40
        with self.assertRaisesRegex(RuntimeError,'head changed'):self.run_main()
        self.api.create_commit.assert_not_called()
    def test_hash_mismatch_blocks_before_api(self):
        self.doc['validation']['sha256']='0'*64;self.save()
        with self.assertRaisesRegex(RuntimeError,'Candidate differs'):self.run_main()
        self.api.repo_info.assert_not_called();self.api.create_commit.assert_not_called()
    def test_dictionary_mismatch_blocks(self):
        self.dictionary.write_text('changed stt_transcript')
        with self.assertRaisesRegex(RuntimeError,'Dictionary differs'):self.run_main()
        self.api.create_commit.assert_not_called()
    def test_full_legacy_schema_checked(self):
        self.doc['validation']['schemas']['judges']['columns'][0][1]='BIGINT';self.save()
        with self.assertRaisesRegex(RuntimeError,'Full schema'):self.run_main()
        self.api.create_commit.assert_not_called()
    def test_uploaded_receipt_survives_failure_and_verify_only_never_uploads(self):
        with patch.object(p,'verify_remote',side_effect=RuntimeError('network interrupted')):
            with self.assertRaisesRegex(RuntimeError,'network interrupted'):self.run_main()
        saved=json.loads(self.receipt.read_text());self.assertEqual(saved['status'],'uploaded_pending_verification');self.assertEqual(saved['commit'],self.commit)
        kwargs=self.api.create_commit.call_args.kwargs;self.assertEqual(kwargs['parent_commit'],self.parent);self.assertEqual(kwargs['num_threads'],1);self.assertEqual(len(kwargs['operations']),4)
        self.api.reset_mock()
        with patch.object(p,'verify_remote',return_value={'main':{'passed':True}}):self.run_main('--verify-only','--commit',self.commit)
        self.api.create_commit.assert_not_called();self.api.repo_info.assert_not_called();self.assertEqual(json.loads(self.receipt.read_text())['status'],'verified')
    def test_existing_receipt_blocks_second_upload(self):
        self.receipt.write_text('{}')
        with self.assertRaises(FileExistsError):self.run_main()
        self.api.create_commit.assert_not_called()
    def test_wal_blocks_publication(self):
        pathlib.Path(str(self.db)+'.wal').write_bytes(b'uncheckpointed')
        with self.assertRaisesRegex(RuntimeError,'has a WAL'):self.run_main()
        self.api.repo_info.assert_not_called();self.api.create_commit.assert_not_called()
    def test_verify_only_without_receipt_records_lineage(self):
        with patch.object(p,'verify_remote',return_value={'main':{'passed':True}}):self.run_main('--verify-only','--commit',self.commit)
        saved=json.loads(self.receipt.read_text());self.assertEqual(saved['previous_commit'],self.parent);self.assertTrue(saved['url'].endswith(self.commit));self.api.create_commit.assert_not_called()
    def test_lfs_identity_must_match(self):
        self.assertEqual(p.remote_identity(self.api,SimpleNamespace(**self.spec),'main',4,'c'*64),'lfs-sha256')
        for info in [SimpleNamespace(size=5,lfs=SimpleNamespace(sha256='c'*64)),SimpleNamespace(size=4,lfs=None),SimpleNamespace(size=4,lfs=SimpleNamespace(sha256='d'*64))]:
            self.api.get_paths_info.return_value=[info]
            with self.assertRaises(RuntimeError):p.remote_identity(self.api,SimpleNamespace(**self.spec),'main',4,'c'*64)
    def test_remote_head_change_is_not_success(self):
        con=Mock();con.execute.return_value.fetchall.return_value=[(1,)]
        with patch.object(p.duckdb,'connect',return_value=con),patch.object(p,'remote_identity',return_value='lfs-sha256'),patch.object(p,'check_tables',return_value=([('judges',1)],{'judges':1})):
            with self.assertRaisesRegex(RuntimeError,'head changed'):p.verify_remote(self.api,SimpleNamespace(**self.spec),self.commit,self.report)
        con.close.assert_called_once()

if __name__=='__main__':unittest.main()
