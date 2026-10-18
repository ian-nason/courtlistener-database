import importlib.util, json, os, pathlib, subprocess, tempfile, unittest
REPO=pathlib.Path(__file__).resolve().parent

class RefreshTests(unittest.TestCase):
    def test_manifest_schema_wins_over_old_cache_and_missing_is_fatal(self):
        spec=importlib.util.spec_from_file_location('court_builder',REPO/'build_database.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);module.RAW=root;module.MANIFEST={'schema':{'file':'schema-2026-09-30.sql'}}
            (root/'schema-2025-01-31.sql').write_text('CREATE TABLE public.fixture (\n    id text\n);')
            (root/'schema-2026-09-30.sql').write_text('CREATE TABLE public.fixture (\n    id integer\n);')
            self.assertEqual(module.load_schema()['fixture'],[('id','integer')])
            (root/'schema-2026-09-30.sql').unlink()
            with self.assertRaises(FileNotFoundError):module.load_schema()

    def test_verified_downloader_failure_propagates(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/'download_data.sh').write_bytes((REPO/'download_data.sh').read_bytes())
            fake=root/'fake-python';fake.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\nexit 22\n');fake.chmod(0o700)
            result=subprocess.run(['bash',str(root/'download_data.sh')],env=dict(os.environ,PYTHON=str(fake)),capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,22);self.assertIn('download_sources.py',result.stdout);self.assertIn('--receipt',result.stdout)
            self.assertFalse((root/'data/raw').exists())

    def test_invalid_manifest_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);(root/'docs').mkdir();(root/'download_data.sh').write_bytes((REPO/'download_data.sh').read_bytes());(root/'docs/bulk_manifest.json').write_text('invalid');(root/'download_sources.py').write_bytes((REPO/'download_sources.py').read_bytes())
            result=subprocess.run(['bash',str(root/'download_data.sh')],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)

    def test_existing_database_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/'existing.duckdb';out.write_bytes(b'preserve this artifact')
            result=subprocess.run([os.sys.executable,str(REPO/'build_database.py'),'--output',str(out)],cwd=REPO,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertEqual(out.read_bytes(),b'preserve this artifact');self.assertIn('Refusing to overwrite',result.stderr)

if __name__=='__main__':unittest.main()
