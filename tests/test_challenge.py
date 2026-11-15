import unittest


class ChallengeTests(unittest.TestCase):
    def test_challenge_preserves_answers_through_join_and_unit_transforms(self):
        from prototype_evals.cases import generate
        from prototype_evals.challenge import complicate, normalize
        from prototype_evals.solve import solve
        from prototype_evals.grade import grade
        for case in generate(23):
            hard = complicate(case)
            answer = solve(normalize(hard['public']))
            self.assertEqual(grade(case['expected'], answer)['score'], 1, case['id'])
            self.assertNotEqual(case['id'], hard['id'])
            self.assertNotIn('expected', hard['public'])

    def test_audit_excludes_later_visits_and_training_people(self):
        from prototype_evals.cases import generate
        from prototype_evals.challenge import complicate, normalize
        case = generate(11)[0]
        hard = complicate(case)
        clean = normalize(hard['public'])
        self.assertEqual(len(clean['rows']), 320)
        self.assertEqual(len({r['patient'] for r in clean['rows']}), 320)
        self.assertEqual({r['split'] for r in clean['rows']}, {'test'})


if __name__ == '__main__':
    unittest.main()
