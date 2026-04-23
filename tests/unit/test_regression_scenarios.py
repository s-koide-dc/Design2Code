# -*- coding: utf-8 -*-
import unittest

from src.config.config_manager import ConfigManager
from src.design_parser.structured_parser import StructuredDesignParser
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.utils.spec_auditor import SpecAuditor


class TestRegressionScenarios(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.parser = StructuredDesignParser()
        self.synthesizer = CodeSynthesizer(self.config)
        self.auditor = SpecAuditor(knowledge_base=self.synthesizer.ukb)

    def _assert_no_spec_issues(self, design_path: str):
        spec = self.parser.parse_design_file(design_path)
        result = self.synthesizer.synthesize_from_structured_spec(
            spec.get("module_name"),
            spec,
            return_trace=True
        )
        issues = self.auditor.audit(spec, result)
        self.assertEqual([], issues, f"Spec issues detected for {design_path}: {issues}")

    def test_env_config_to_console(self):
        self._assert_no_spec_issues("scenarios/EnvConfigToConsole.design.md")

    def test_stdin_to_stdout_transform(self):
        self._assert_no_spec_issues("scenarios/StdinToStdoutTransform.design.md")

    def test_csv_sales_aggregation(self):
        self._assert_no_spec_issues("scenarios/CsvSalesAggregation.design.md")

    def test_daily_inventory_sync(self):
        self._assert_no_spec_issues("scenarios/DailyInventorySync.design.md")

    def test_sync_external_data(self):
        self._assert_no_spec_issues("scenarios/SyncExternalData.design.md")

    def test_fetch_product_inventory(self):
        self._assert_no_spec_issues("scenarios/FetchProductInventory.design.md")

    def test_batch_process_products(self):
        self._assert_no_spec_issues("scenarios/BatchProcessProducts.design.md")

    def test_process_active_users(self):
        self._assert_no_spec_issues("scenarios/ProcessActiveUsers.design.md")

    def test_complex_linq_search(self):
        self._assert_no_spec_issues("scenarios/ComplexLinqSearch.design.md")

    def test_ephemeral_calculation(self):
        self._assert_no_spec_issues("scenarios/EphemeralCalculation.design.md")

    def test_robust_config_loader(self):
        self._assert_no_spec_issues("scenarios/RobustConfigLoader.design.md")

    def test_secure_order_processing(self):
        self._assert_no_spec_issues("scenarios/SecureOrderProcessing.design.md")

    def test_state_update_persist(self):
        self._assert_no_spec_issues("scenarios/StateUpdatePersist.design.md")

    def test_user_report_generator(self):
        self._assert_no_spec_issues("scenarios/UserReportGenerator.design.md")

    def test_aggregation_summary(self):
        self._assert_no_spec_issues("scenarios/AggregationSummary.design.md")

    def test_calculate_order_discount(self):
        self._assert_no_spec_issues("scenarios/CalculateOrderDiscount.design.md")


if __name__ == "__main__":
    unittest.main()
