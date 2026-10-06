from pathlib import Path
import tempfile
import unittest
from head_workflow import Session,make_roster,pin,write_fresh


class BudgetExtensionTests(unittest.TestCase):
    def test_legacy_adoption_requires_settled_complete_branch_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);roster=root/'roster.json';write_fresh(roster,make_roster())
            parent=Session.create(root/'parent',roster)
            child=parent.fork_revision(root/'child',['human-male-01'],'reference',[pin(roster)])
            (parent.root/'spending-owner.json').unlink()  # Simulate pre-ownership history.
            with self.assertRaisesRegex(ValueError,'Legacy session'):
                child.fork_revision(root/'blocked',['human-male-01'],'reference',[pin(roster)])
            proof={'kind':'srn-head-spending-reconciliation','approved':True,'session':pin(child.root/'session.json'),
                   'creditUsed':0,'creditCap':300,'sessions':[pin(p.root/'session.json') for p in (parent,child)],
                   'events':[pin(p) for s in (parent,child) for p in sorted((s.root/'events').glob('*.json'))]}
            bad=root/'bad.json';write_fresh(bad,{**proof,'events':[]})
            with self.assertRaises(ValueError):child.adopt_spending(bad)
            approval=root/'proof.json';write_fresh(approval,proof);child.adopt_spending(approval)
            self.assertEqual(child.spending_owner(parent.root/'spending-owner.json'),child.root)
            with self.assertRaisesRegex(ValueError,'already established'):child.adopt_spending(approval)

    def test_extension_preserves_spending_and_scopes_new_paid_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);roster=root/'roster.json';write_fresh(roster,make_roster())
            parent=Session.create(root/'parent',roster)
            parent.append('reserved',requestId='old',estimatedCredits=255)
            parent.append('settled',requestId='old',credits=255)
            approval=root/'approval.json';ids=['elf-male-01','dwarf-male-01','orc-male-01']
            write_fresh(approval,{'kind':'srn-head-budget-approval','approved':True,'previousCap':300,
                'newCap':405,'designs':ids,'userInstruction':'Raise to 405'})
            snapshot=(parent.root/'session.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'approval required'):
                parent.fork_revision(root/'missing',ids,'reference',[pin(roster)],credit_cap=405)
            with self.assertRaisesRegex(ValueError,'scope or ceiling'):
                parent.fork_revision(root/'wrong',ids,'reference',[pin(approval)],credit_cap=450,budget_approval=approval)
            child=parent.fork_revision(root/'child',ids,'reference',[pin(approval)],credit_cap=405,budget_approval=approval)
            self.assertEqual(child.credit_used(),255);self.assertEqual(child.config['creditCap'],405)
            self.assertEqual((parent.root/'session.json').read_bytes(),snapshot)
            with self.assertRaisesRegex(ValueError,'outside approved'):
                child.reserve('human-male-01','extra','retexture',10,[pin(roster)],{})
            descendant=child.fork_revision(root/'next',['elf-male-01'],'fitting',[pin(roster)])
            self.assertEqual(descendant.config['creditCap'],405)
            approval.write_text('{}')
            with self.assertRaises(ValueError):Session(child.root)


if __name__=='__main__':unittest.main()
