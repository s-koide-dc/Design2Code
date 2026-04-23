# -*- coding: utf-8 -*-
import unittest

from src.design_parser.project_spec_parser import ProjectSpecParser


class TestProjectSpecParser(unittest.TestCase):
    def test_parse_project_spec(self):
        content = """# UsersWebApi
## 1. Project Spec
### Tech
- **Framework**: ASP.NET Core
- **Language**: C#
- **Style**: WebAPI
- **RepositoryPolicy**: Enabled

### Data Access
- **Provider**: SqlServer
- **Strategy**: Dapper
- **Connection**: AppSettings:ConnectionStrings:Default

### Modules
- **Controller**: UsersController
  - Routes:
    - GET /users
    - GET /users/{id}
- **Service**: UserService
  - Methods:
    - GetUsers()
    - GetUserById(int id)
- **Repository**: UserRepository
  - Methods:
    - FetchAll()
    - FetchById(int id)
    - Insert(User user)

### Entities / DTO
- **Entity**: User
  - Id:int, Name:string, Email:string
- **DTO**: UserCreateRequest
  - Name:string, Email:string
"""
        parser = ProjectSpecParser()
        result = parser.parse_content(content)
        spec = result.get("spec", {})
        self.assertEqual("UsersWebApi", result.get("project_name"))
        self.assertEqual("ASP.NET Core", spec.get("tech", {}).get("Framework"))
        self.assertEqual("Enabled", spec.get("tech", {}).get("RepositoryPolicy"))
        self.assertEqual("SqlServer", spec.get("data_access", {}).get("Provider"))
        modules = spec.get("modules", [])
        self.assertEqual(3, len(modules))
        self.assertEqual("UsersController", modules[0].get("name"))
        self.assertIn("GET /users", modules[0].get("routes", []))
        entities = spec.get("entities", [])
        self.assertEqual("User", entities[0].get("name"))
        dtos = spec.get("dtos", [])
        self.assertEqual("UserCreateRequest", dtos[0].get("name"))


if __name__ == "__main__":
    unittest.main()
