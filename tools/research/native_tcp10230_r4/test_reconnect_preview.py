import unittest
from reconnect_preview import preview_retry,successful_connect_reset
class RetryModelTests(unittest.TestCase):
    def test_initial_pause_and_rate_preview(self):
        p=successful_connect_reset();self.assertEqual(p,25)
        r=preview_retry(p);self.assertEqual(r.delay_ms,260)
        self.assertTrue(r.preview_rate_request_queued)
        self.assertGreater(r.pause_after,p)
    def test_subsequent_retry_no_rate_preview(self):
        r=preview_retry(preview_retry(25).pause_after)
        self.assertFalse(r.preview_rate_request_queued)
        self.assertEqual(r.delay_ms,360)
    def test_backoff_does_not_grow_after_801(self):
        r=preview_retry(802.0)
        self.assertEqual(r.pause_after,802.0)
        self.assertEqual(r.delay_ms,8030)
    def test_reset_each_successful_connection(self):
        self.assertEqual(successful_connect_reset(),25.0)
if __name__=='__main__':unittest.main()
