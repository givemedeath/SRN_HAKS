"""Independent regression retained from the initial duplicate-ID investigation.

The root guard now rejects duplicate IDs, and the ordinary discovered suite also
covers duplicate nodes/interfaces. Historical failing receipts and source
snapshots remain unchanged; this case can still be run explicitly.
"""
import copy
import unittest

import generate_target_qwen_reference as qwen
from test_generate_target_qwen_reference import workflow_fixture


class PendingDuplicateNodeInventoryTests(unittest.TestCase):
    def test_duplicate_subgraph_node_id_is_rejected_even_when_type_matches(self):
        workflow, schemas = workflow_fixture()
        group = workflow['definitions']['subgraphs'][0]
        group['nodes'].append(copy.deepcopy(group['nodes'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate.*node'):
            qwen.expand_graph(workflow, schemas, 'explicit prompt', 42,
                              ['guide.png'], [1536, 1024], 'test')


if __name__ == '__main__': unittest.main()
