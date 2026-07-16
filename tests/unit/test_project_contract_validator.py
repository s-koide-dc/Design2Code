import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.code_generation.project_contract_validator import validate_generated_project_contract, validate_project_contract


class ProjectContractValidatorTests(unittest.TestCase):
    def test_valid_layered_contract_has_no_blocking_issues(self):
        project = {
            "spec": {
                "modules": [
                    {"type": "Controller", "name": "UsersController", "routes": ["GET /users"]},
                    {"type": "Service", "name": "UserService", "methods": ["GetUsers(): List<UserResponse>"]},
                    {"type": "Repository", "name": "UserRepository", "methods": ["FetchAll(): List<User>"]},
                ],
                "entities": [{"name": "User"}],
                "dtos": [{"name": "UserResponse"}],
                "method_specs": {
                    "UserService.GetUsers": {"output": "List<UserResponse>"},
                    "UserRepository.FetchAll": {"output": "List<User>"},
                },
            }
        }
        self.assertEqual([], validate_project_contract(project))

    def test_return_type_mismatch_is_blocking(self):
        project = {
            "spec": {
                "modules": [
                    {"type": "Service", "name": "UserService", "methods": ["GetUsers(): List<UserResponse>"]},
                ],
                "dtos": [{"name": "UserResponse"}],
                "method_specs": {"UserService.GetUsers": {"output": "UserResponse"}},
            }
        }
        issues = validate_project_contract(project)
        self.assertTrue(any(issue.code == "method_return_mismatch" and issue.blocking for issue in issues))

    def test_missing_method_spec_is_warning_for_default_generation(self):
        project = {
            "spec": {
                "modules": [{"type": "Service", "name": "UserService", "methods": ["GetUsers(): List<User>"]}],
                "entities": [{"name": "User"}],
            }
        }
        issues = validate_project_contract(project)
        self.assertEqual(["method_spec_missing"], [issue.code for issue in issues])
        self.assertFalse(issues[0].blocking)

    def test_generated_project_links_layers_and_di_registration(self):
        project = {
            "spec": {
                "modules": [
                    {"type": "Controller", "name": "UsersController", "routes": ["GET /users"]},
                    {"type": "Service", "name": "UserService", "methods": ["GetUsers(): List<User>"]},
                    {"type": "Repository", "name": "UserRepository", "methods": ["FetchAll(): List<User>"]},
                ]
            }
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Controllers").mkdir()
            (root / "Services").mkdir()
            (root / "Repositories").mkdir()
            (root / "Program.cs").write_text(
                "builder.Services.AddScoped<IUserService, UserService>();\n"
                "builder.Services.AddScoped<IUserRepository, UserRepository>();\n",
                encoding="utf-8",
            )
            (root / "Controllers/UsersController.cs").write_text(
                "private readonly IUserService _service;\n_service.GetUsers();\n", encoding="utf-8"
            )
            (root / "Services/UserService.cs").write_text("public class UserService : IUserService", encoding="utf-8")
            (root / "Repositories/UserRepository.cs").write_text("public class UserRepository : IUserRepository", encoding="utf-8")
            self.assertEqual([], validate_generated_project_contract(project, directory))


if __name__ == "__main__":
    unittest.main()
