import unittest

from panel import main as panel_main


class PanelSelectorSummaryTests(unittest.TestCase):
    def test_prefers_configured_selector_group(self) -> None:
        proxies = {
            panel_main.SELECTOR_TAG: {"type": "Selector", "all": ["node-a"], "now": "node-a"},
            "其它分组": {"type": "Selector", "all": ["node-b"], "now": "node-b"},
        }

        tag, selector, warning = panel_main._find_selector_proxy(proxies)

        self.assertEqual(panel_main.SELECTOR_TAG, tag)
        self.assertEqual(["node-a"], selector["all"])
        self.assertEqual("", warning)

    def test_falls_back_to_actual_selector_group(self) -> None:
        proxies = {
            "自动选择": {"type": "Selector", "all": ["node-a"], "now": "node-a"},
            "direct": {"type": "Direct"},
        }

        tag, selector, warning = panel_main._find_selector_proxy(proxies)

        self.assertEqual("自动选择", tag)
        self.assertEqual(["node-a"], selector["all"])
        self.assertIn(panel_main.SELECTOR_TAG, warning)

    def test_reports_missing_selector_group(self) -> None:
        tag, selector, warning = panel_main._find_selector_proxy({"direct": {"type": "Direct"}})

        self.assertEqual(panel_main.SELECTOR_TAG, tag)
        self.assertIsNone(selector)
        self.assertIn("未找到有效 selector 分组", warning)


    def test_counts_real_nodes_in_configured_selector(self) -> None:
        cfg = {
            "outbounds": [
                {"type": "selector", "tag": panel_main.SELECTOR_TAG, "outbounds": ["node-a", "direct", "node-b"]},
                {"type": "direct", "tag": "direct"},
            ]
        }

        self.assertEqual(panel_main._configured_selector_node_count(cfg), 2)

    def test_counts_fallback_selector_when_configured_tag_missing(self) -> None:
        cfg = {
            "outbounds": [
                {"type": "selector", "tag": "AUTO", "outbounds": ["node-a", "direct"]},
            ]
        }

        self.assertEqual(panel_main._configured_selector_node_count(cfg), 1)


if __name__ == "__main__":
    unittest.main()
