import hashlib,io,pathlib,tempfile,unittest
from unittest.mock import patch
import download_sources as d
class Response(io.BytesIO):
    headers={'Content-Length':'4','ETag':'"stable"'}
class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.item={'file':'source.bz2','url':'https://example.invalid/source.bz2','size':4,'etag':'"stable"'};self.identity={'size':4,'etag':'"stable"','last_modified_http':'today'}
    def tearDown(self):self.tmp.cleanup()
    def test_verified_download_installs_exact_bytes(self):
        with patch.object(d,'identity',return_value=self.identity),patch.object(d.urllib.request,'urlopen',return_value=Response(b'data')):
            result=d.acquire(self.item,self.root)
        self.assertEqual((self.root/'source.bz2').read_bytes(),b'data');self.assertEqual(result['sha256'],hashlib.sha256(b'data').hexdigest());self.assertTrue(result['post_download_identity_verified'])
    def test_unknown_existing_cache_is_preserved(self):
        p=self.root/'source.bz2';p.write_bytes(b'keep')
        with patch.object(d,'identity',return_value=self.identity),patch.object(d.urllib.request,'urlopen') as get:
            with self.assertRaises(FileExistsError):d.acquire(self.item,self.root)
            get.assert_not_called()
        self.assertEqual(p.read_bytes(),b'keep')
    def test_source_change_never_installs(self):
        with patch.object(d,'identity',side_effect=[self.identity,dict(self.identity,etag='"changed"')]),patch.object(d.urllib.request,'urlopen',return_value=Response(b'data')):
            with self.assertRaisesRegex(ValueError,'after GET'):d.acquire(self.item,self.root)
        self.assertFalse((self.root/'source.bz2').exists())
    def test_truncated_get_never_installs(self):
        with patch.object(d,'identity',return_value=self.identity),patch.object(d.urllib.request,'urlopen',return_value=Response(b'dat')):
            with self.assertRaisesRegex(ValueError,'Truncated'):d.acquire(self.item,self.root)
        self.assertFalse((self.root/'source.bz2').exists())
    def test_pinned_sha_mismatch_never_installs(self):
        item=dict(self.item,sha256='0'*64)
        with patch.object(d,'identity',return_value=self.identity),patch.object(d.urllib.request,'urlopen',return_value=Response(b'data')):
            with self.assertRaisesRegex(ValueError,'checksum differs'):d.acquire(item,self.root)
        self.assertFalse((self.root/'source.bz2').exists())
    def test_path_escape_is_rejected(self):
        with self.assertRaises(ValueError):d.acquire(dict(self.item,file='../outside'),self.root)
if __name__=='__main__':unittest.main()
