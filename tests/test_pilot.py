import unittest


class PilotTests(unittest.TestCase):
    def test_cli_synthetic_error_message_is_not_model_evidence(self):
        from research_evals.pilot import model_response_ids
        self.assertEqual(model_response_ids(['<synthetic>']), [])
        self.assertEqual(model_response_ids(['claude-opus-5-5', '<synthetic>', 'claude-opus-5-5']),
                         ['claude-opus-5-5'])


if __name__ == '__main__':
    unittest.main()
