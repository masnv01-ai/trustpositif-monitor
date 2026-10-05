import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
import updater as u

class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(u,'DATA_FILE',Path(self.tmp.name)/'domains.txt');self.patch.start()
    def tearDown(self): self.patch.stop();self.tmp.cleanup()
    def response(self, content, content_type='text/plain'):
        r=Mock();r.content=content;r.headers={'Content-Type':content_type};r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False);return r
    def valid_list(self): return ('\n'.join(f'example{i}.com' for i in range(12))).encode()
    def test_normalize(self):
        self.assertEqual(u.normalize_domain(' HTTPS://WWW.Example.COM./path?q=1 '),'example.com')
        self.assertEqual(u.normalize_domain('bücher.de'),'xn--bcher-kva.de')
        for value in ['javascript:alert(1)','ftp://example.com','https://user:pass@example.com','a b.com','-x.com','example.com:99999',None,'localhost']:
            self.assertEqual(u.normalize_domain(value),'',value)
    def test_reject_html_and_small_list(self):
        with self.assertRaises(ValueError):u.parse_blocklist(b'<html>'+self.valid_list()+b'</html>')
        with self.assertRaises(ValueError):u.parse_blocklist(self.valid_list(),'text/html')
        with self.assertRaises(ValueError):u.parse_blocklist(b'example.com')
    def test_parsing(self):
        self.assertEqual(len(u.parse_blocklist(b'# comment.example\n'+self.valid_list())),12)
    def test_atomic_download(self):
        u.DATA_FILE.write_text('old')
        with patch.object(u.requests,'get',return_value=self.response(self.valid_list())):
            self.assertEqual(len(u.download_blocklist()),12)
        self.assertEqual(u.DATA_FILE.read_bytes(),self.valid_list())
    def test_bad_download_does_not_update(self):
        ref=Mock()
        with patch.object(u.requests,'get',return_value=self.response(b'<html>error</html>')):
            self.assertFalse(u.run_once(ref))
        ref.get.assert_not_called();ref.update.assert_not_called()
        self.assertFalse(u.DATA_FILE.exists())
    def test_network_failure(self):
        ref=Mock()
        with patch.object(u.requests,'get',side_effect=requests.Timeout('timeout')):
            self.assertFalse(u.run_once(ref))
        ref.update.assert_not_called()
    def test_updates_and_invalid_domain(self):
        ref=Mock();ref.get.return_value={'a':{'link':'https://www.example.com/p'},'b':{'domain':'safe.com'},'c':{'link':'javascript:alert(1)','blocked':False},'ignored':42}
        self.assertEqual(u.check_firebase_records(ref,{'example.com'}),2)
        data=ref.update.call_args.args[0]
        self.assertTrue(data['a/blocked'])
        self.assertEqual(set(data), {'a/blocked','a/status','a/checked_at'})
        self.assertEqual(data['a/status'],'diblokir')
    def test_failed_update_removes_download(self):
        ref=Mock();ref.get.return_value={'a':{'link':'example0.com'}};ref.update.side_effect=RuntimeError('update failed')
        with patch.object(u.requests,'get',return_value=self.response(self.valid_list())):
            self.assertFalse(u.run_once(ref))
        self.assertFalse(u.DATA_FILE.exists())
    def test_success_removes_download(self):
        ref=Mock();ref.get.return_value={'a':{'link':'example0.com'}}
        with patch.object(u.requests,'get',return_value=self.response(self.valid_list())):
            self.assertTrue(u.run_once(ref))
        self.assertFalse(u.DATA_FILE.exists())
    def test_unlisted_and_previously_blocked_remain_unchanged(self):
        ref=Mock();ref.get.return_value={'a':{'domain':'safe.com','blocked':True,'status':'diblokir'},'b':{'domain':'other.com','blocked':False}}
        self.assertEqual(u.check_firebase_records(ref,{'example.com'}),2)
        ref.update.assert_not_called()
    def test_already_blocked_is_not_written_again(self):
        ref=Mock();ref.get.return_value={'a':{'domain':'example.com','blocked':True,'status':'diblokir'}}
        u.check_firebase_records(ref,{'example.com'})
        ref.update.assert_not_called()
    def test_cli_failure_and_source_mode(self):
        with patch.object(u,'connect_firebase',side_effect=RuntimeError('missing credentials')):
            self.assertEqual(u.main(['--once']),1)
        with patch.object(u,'download_blocklist',return_value={'example.com'}),patch.object(u,'connect_firebase') as connect:
            self.assertEqual(u.main(['--validate-source']),0);connect.assert_not_called()

if __name__=='__main__':unittest.main()
