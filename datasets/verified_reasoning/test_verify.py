"""CPU behavioral regressions: equivalent answers and opposing claims in pairs.

These are deliberately targeted software tests, not an estimated checker error
rate on model completions, and not model capability tests. Standard library only.
"""
import importlib.util
import json
from pathlib import Path
import unittest
import verify

CASES = []
def case(name, reply, gold, expected, category='arithmetic', status=None):
    CASES.append({'id':name,'reply':reply,'row':{'answer':gold,'category':category},'expected':expected,'status':status})

case('reported_remainder_opposite', 'Answer: 6 full trays, 2 short', '6 full trays, 2 left over', False)
case('reported_negated_unknown', 'Answer: This is not unknown; the result is known', 'Cannot be determined', False, 'unanswerable')
for i,(a,b) in enumerate([('7 full bags, 3 left over','7 full bags, 3 short'),('No, £91 short','No, £91 to spare'),('Yes, €18 to spare','Yes, €18 short'),('Nothing; $40 should be refunded','$40 is due')]):
    case(f'polarity_positive_{i}', 'Answer: '+a, a, True)
    case(f'polarity_negative_{i}', 'Answer: '+b, a, False)
for i,(pred,gold) in enumerate([('6.1','$6.10'),('$1,234.50','$1234.50'),('-$2.50','$-2.50'),('−£12.25','£-12.25'),('1/2','0.5'),('0.5 kg','500 g'),('500g','0.5 kg'),('90 minutes','1 h 30 min'),('2 hours','120 minutes')]):
    case(f'numeric_equivalent_{i}','Answer: '+pred,gold,True)
for i,(pred,gold) in enumerate([('2.50','$-2.50'),('-2.50','$2.50'),('$8','£8'),('€8','$8'),('8 kg','8 g'),('8 minutes','8 days'),('5 9 5','5 full bags, 5 left over'),('20A','20'),('5 or 6','5'),('not 5','5'),('5; actually 7','5'),('5 and 5','5'),('8 full boxes, 2 left over','8 full trays, 2 left over')]):
    case(f'numeric_wrong_{i}','Answer: '+pred,gold,False)
for i,text in enumerate(['Cannot be determined','Unknown','We cannot tell from the information given',"We can't tell from the information given.",'There is insufficient information','It is not known','It depends','It is impossible to know from the given information']):
    case(f'uncertain_equivalent_{i}','Answer: '+text,'Cannot be determined',True,'unanswerable')
for i,text in enumerate(['not unknown','The result is known','It can be determined','It is not impossible to determine','Unknown, but the answer is 5','The unknown is 5','I do not think it is unknown','Cannot be determined; definitely heads']):
    case(f'uncertain_negated_{i}','Answer: '+text,'Cannot be determined',False,'unanswerable')
for i,(pred,gold) in enumerate([('The premises are contradictory','Contradictory premise'),('There is a contradiction','Contradictory premise'),('Nothing left','There is none'),('The box is empty','There is none'),('You never mentioned the price','You did not say'),('The price was not given','You did not say')]):
    case(f'absence_equivalent_{i}','Answer: '+pred,gold,True,'unanswerable')
for i,(pred,gold) in enumerate([('The premises are not contradictory','Contradictory premise'),('It is not empty','There is none'),('There is none, except two','There is none'),('You did say the price','You did not say'),('You never mentioned the price, but it is £5','You did not say')]):
    case(f'absence_opposite_{i}','Answer: '+pred,gold,False,'unanswerable')
for i,(pred,gold) in enumerate([('9:30 am','09:30'),('09:30','9:30 am'),('12:00 am','00:00'),('12:00 pm','12:00'),('Monday 5:29 pm','Monday 17:29'),('April 1, 2024','1 April 2024'),('2024-04-01','1 April 2024'),('1st April 2024','1 April 2024')]):
    case(f'calendar_equivalent_{i}','Answer: '+pred,gold,True,'dates_times')
for i,(pred,gold) in enumerate([('Monday 17:29','Tuesday 17:29'),('Not Monday','Monday'),('May 1, 2024','1 April 2024'),('1 April 2025','1 April 2024'),('25:30','01:30'),('13:30 pm','13:30'),('09:77','10:17'),('not 09:30','09:30')]):
    case(f'calendar_wrong_{i}','Answer: '+pred,gold,False,'dates_times')
for i,(pred,gold,expected) in enumerate([('Omar','Omar',True),('The answer is Omar.','Omar',True),('not Omar','Omar',False),('Omar is not the answer','Omar',False),('Omar or Nina','Omar',False),('Omara','Omar',False),('third','third',True),('3rd','third',True),('fourth','third',False),('No','Yes',False),('Yes, but no','Yes',False),('Yes, unknown','Yes',False),('Yes, 08:21','Yes, 08:21',True),('Yes, 08:12','Yes, 08:21',False)]):
    case(f'label_{i}','Answer: '+pred,gold,expected,'logic')
for i,(pred,gold,expected) in enumerate([('BA 117','BA 117',True),('BA117','BA 117',True),('117','BA 117',False),('XX117','BA 117',False),('22A','22A',True),('22B','22A',False),('122A','22A',False),('red_owl7','red_owl7',True),('red_owl7x','red_owl7',False),('Pack 2','Pack 1',False),('Pack 1','Pack 1',True)]):
    case(f'code_{i}','Answer: '+pred,gold,expected,'memory')
case('list_equivalent','Answer: drum, guitar and flute','guitar, flute, drum',True,'memory')
case('list_missing','Answer: drum and flute','guitar, flute, drum',False,'memory')
case('list_duplicate','Answer: drum, guitar, flute, flute','guitar, flute, drum',False,'memory')
source='Report Blue: the gate opened at 08:21'
for i,(pred,expected) in enumerate([('Report Blue: the gate opened at 08:21',True),('Report Blue says the gate opened at 8:21 am',True),('Report Blue: 08:21',True),('Report Red: the gate opened at 08:21',False),('Report Blue: the gate opened at 08:12',False),('Report Blue: the gate closed at 08:21',False),('Report Red says 08:21; Report Blue was withdrawn',False),('Report Blue: 08:21; Report Red: 08:12',False)]):
    case(f'source_{i}','Answer: '+pred,source,expected,'conflicting_sources')
case('multiple_final_conflict','Answer: 5\nAnswer: 7','5',False,status='ambiguous')
case('multiple_final_conflict_other_gold','Answer: 5\nAnswer: 7','7',False,status='ambiguous')
case('multiple_final_equivalent','Answer: $6.10\nAnswer: 6.1','$6.10',True)
case('explicit_final_revision','Working answer: 5\nFinal answer: 7','7',True)
case('explicit_correction','Answer: 5\nCorrection: 7','7',True)
case('boxed','Working... \\boxed{6.10}','$6.10',True)
case('boxed_conflict','\\boxed{5} and \\boxed{7}','5',False,status='ambiguous')
grid='1 0\n0 1'
case('grid_exact','Output:\n'+grid,grid,True,'arc_grids')
case('grid_json','Answer: [[1,0],[0,1]]',grid,True,'arc_grids')
case('grid_fenced','Output:\n```text\n'+grid+'\n```',grid,True,'arc_grids')
case('grid_wrong_cell','Output:\n1 0\n1 1',grid,False,'arc_grids')
case('grid_flattened','Output: 1 0 0 1',grid,False,'arc_grids')
case('grid_ragged','Output:\n1 0\n0',grid,False,'arc_grids')
case('grid_bool','Output: [[true,0],[0,1]]',grid,False,'arc_grids')
case('grid_two_digit','Output:\n10 0\n0 1',grid,False,'arc_grids')
case('grid_earlier_correct','Example:\n'+grid+'\n\nOutput:\n0 0\n0 0',grid,False,'arc_grids')
case('grid_conflicting_final','Output:\n'+grid+'\n\nOutput:\n0 0\n0 0',grid,False,'arc_grids',status='ambiguous')
for i,text in enumerate(['5 if the rules change','5, but that is wrong','5; the answer is unknown','approximately 5','1/0','9'*5000]):
    case(f'unsupported_numeric_claim_{i}','Answer: '+text,'5',False)
case('conditional_yes','Answer: Yes, if it is switched on','Yes',False,'logic',status='ambiguous')
case('too_many_final_claims','\n'.join(['Answer: 5']*33),'5',False,status='ambiguous')

class VerifierTests(unittest.TestCase):
    def test_behavioral_cases(self):
        for c in CASES:
            with self.subTest(case=c['id']):
                result=verify.judge(c['reply'],c['row'])
                self.assertEqual(verify.check(c['reply'],c['row']),c['expected'],result)
                if c['status']:self.assertEqual(result['status'],c['status'])
    def test_reply_bound(self):
        self.assertEqual(verify.judge('5'*(verify.MAX_REPLY_CHARACTERS+1),{'answer':'5'})['status'],'unparseable')
    def test_invalid_reference(self):
        with self.assertRaises(ValueError):verify.judge('5',{'answer':''})

def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(VerifierTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print(json.dumps({'behavioral_cases':len(CASES),'framework_tests':result.testsRun,'passed':True}))

if __name__=='__main__':main()
