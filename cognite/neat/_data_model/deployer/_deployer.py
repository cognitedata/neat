from dataclasses import dataclass

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessResultProducer
from cognite.neat._data_model.deployer.data_classes import SeverityType
from cognite.neat._data_model.models.dms import RequestSchema

from .data_classes import DeploymentResult


@dataclass
class DeploymentOptions:
    """Configuration options for deployment."""

    dry_run: bool = True
    auto_rollback: bool = True
    max_severity: SeverityType = "safe"


class SchemaDeployer(OnSuccessResultProducer):
    def __init__(self, client: NeatClient, options: DeploymentOptions | None = None) -> None:
        super().__init__(client)
        self.client: NeatClient = client
        self.options: DeploymentOptions = options or DeploymentOptions()
        self._results: DeploymentResult | None = None

    @property
    def results(self) -> DeploymentResult:
        if self._results is None:
            raise RuntimeError("SchemaDeployer has not been run yet.")
        return self._results

    def run(self, data_model: RequestSchema) -> None:
        self._snapshot = self._fetch_cdf_state()

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self._create_deployment_plan()

        # Step 3: Analyze changes and collect issues
        self._analyze_changes(plan)

        # Step 4: Check if deployment should proceed
        if not self._should_proceed(plan):
            return DeploymentResult(
                success=False,
                plan=plan,
                applied_changes=[],
                failed_changes=[],
                snapshot=None,
                issues=self.issues,
                dry_run=self.options.dry_run,
            )

        # Step 5: If dry-run, return plan without applying
        if self.options.dry_run:
            return DeploymentResult(
                success=True,
                plan=plan,
                applied_changes=[],
                failed_changes=[],
                snapshot=None,
                issues=self.issues,
                dry_run=True,
            )

        # Step 6: Apply changes
        result = self._apply_changes(plan)

        # Step 7: Rollback if failed and auto_rollback is enabled
        if not result.success and self.options.auto_rollback and self._snapshot:
            self._rollback(self._snapshot)

        return result
