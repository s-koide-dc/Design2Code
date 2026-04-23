using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using static Microsoft.CodeAnalysis.CSharp.SyntaxFactory;

namespace CodeBuilder;

public class Blueprint
{
    [JsonPropertyName("namespace")] public string Namespace { get; set; } = "Generated";
    [JsonPropertyName("class_name")] public string ClassName { get; set; } = "GeneratedProcessor";
    [JsonPropertyName("usings")] public List<string> Usings { get; set; } = new();
    [JsonPropertyName("fields")] public List<FieldBlueprint> Fields { get; set; } = new();
    [JsonPropertyName("methods")] public List<MethodBlueprint> Methods { get; set; } = new();
    [JsonPropertyName("extra_classes")] public List<ClassBlueprint> ExtraClasses { get; set; } = new();
    [JsonPropertyName("extra_code")] public List<string> ExtraCode { get; set; } = new();
    [JsonPropertyName("optimize")] public bool Optimize { get; set; } = false;
}

public class FieldBlueprint
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("type")] public string Type { get; set; } = "";
}

public class ClassBlueprint
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("properties")] public List<PropertyBlueprint> Properties { get; set; } = new();
}

public class PropertyBlueprint
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("type")] public string Type { get; set; } = "string";
    [JsonPropertyName("attributes")] public List<string> Attributes { get; set; } = new();
}

public class ParameterBlueprint
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("type")] public string Type { get; set; } = "object";
}

public class MethodBlueprint
{
    [JsonPropertyName("name")] public string Name { get; set; } = "Execute";
    [JsonPropertyName("return_type")] public string ReturnType { get; set; } = "void";
    [JsonPropertyName("is_async")] public bool IsAsync { get; set; } = false;
    [JsonPropertyName("params")] public List<ParameterBlueprint> Params { get; set; } = new();
    [JsonPropertyName("body")] public List<StatementBlueprint> Body { get; set; } = new();
}

public class StatementBlueprint
{
    [JsonPropertyName("type")] public string Type { get; set; } = "";
    [JsonPropertyName("var_name")] public string VarName { get; set; } = "";
    [JsonPropertyName("var_type")] public string? VarType { get; set; } = null;
    [JsonPropertyName("value")] public string Value { get; set; } = "";
    [JsonPropertyName("method")] public string Method { get; set; } = "";
    [JsonPropertyName("args")] public List<string> Args { get; set; } = new();
    [JsonPropertyName("out_var")] public string OutVar { get; set; } = "";
    [JsonPropertyName("condition")] public string Condition { get; set; } = "";
    [JsonPropertyName("source")] public string Source { get; set; } = "";
    [JsonPropertyName("collection")] public string Collection { get; set; } = "";
    [JsonPropertyName("item_name")] public string ItemName { get; set; } = "";
    [JsonPropertyName("item_var")] public string ItemVar { get; set; } = "";
    [JsonPropertyName("is_async")] public bool IsAsync { get; set; } = false;
    [JsonPropertyName("body")] public List<StatementBlueprint> Body { get; set; } = new();
    [JsonPropertyName("else_body")] public List<StatementBlueprint> ElseBody { get; set; } = new();
    [JsonPropertyName("catch_body")] public List<StatementBlueprint> CatchBody { get; set; } = new();
    [JsonPropertyName("text")] public string Text { get; set; } = ""; 
    [JsonPropertyName("code")] public string Code { get; set; } = ""; 
}

class Program
{
    static void Main(string[] args)
    {
        try
        {
            const string jsonStartMarker = "__CODEBUILDER_JSON_START__";
            const string jsonEndMarker = "__CODEBUILDER_JSON_END__";
            string inputJson;
            using (var ms = new MemoryStream())
            {
                Console.OpenStandardInput().CopyTo(ms);
                inputJson = Encoding.UTF8.GetString(ms.ToArray()).Trim('\uFEFF');
            }
            if (string.IsNullOrWhiteSpace(inputJson)) return;
            var bp = JsonSerializer.Deserialize<Blueprint>(inputJson, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (bp == null) throw new Exception("Deserialization result is null.");
            var code = GenerateCode(bp);
            
            // 診断機能の追加: 生成したコードをパースして基本的なエラーをチェック
            var tree = CSharpSyntaxTree.ParseText(code);
            var diagnostics = tree.GetDiagnostics()
                .Where(d => d.Severity == DiagnosticSeverity.Error)
                .Select(d => {
                    var lineSpan = d.Location.GetLineSpan();
                    var text = tree.GetText().ToString(d.Location.SourceSpan);
                    return new { 
                        id = d.Id, 
                        message = d.GetMessage(), 
                        line = lineSpan.StartLinePosition.Line + 1,
                        symbol = text // 構造的に問題のテキストを抽出
                    };
                })
                .ToList();

            Console.WriteLine(jsonStartMarker);
            Console.WriteLine(JsonSerializer.Serialize(new { 
                status = "success", 
                code = bp.Optimize ? OptimizeCode(code) : code, 
                diagnostics = diagnostics,
                has_errors = diagnostics.Any()
            }));
            Console.WriteLine(jsonEndMarker);
        }
        catch (Exception ex)
        {
            const string jsonStartMarker = "__CODEBUILDER_JSON_START__";
            const string jsonEndMarker = "__CODEBUILDER_JSON_END__";
            Console.WriteLine(jsonStartMarker);
            Console.WriteLine(JsonSerializer.Serialize(new { status = "error", message = ex.Message }));
            Console.WriteLine(jsonEndMarker);
        }
    }

    static string GenerateCode(Blueprint bp)
    {
        var classDecl = ClassDeclaration(bp.ClassName ?? "GeneratedProcessor")
            .AddModifiers(Token(SyntaxKind.PublicKeyword), Token(SyntaxKind.PartialKeyword))
            .WithLeadingTrivia(Comment("// Rendered by updated CodeBuilder\n"));

        // Add Fields
        var fields = bp.Fields ?? new();
        foreach (var field in fields)
        {
            var fieldDecl = FieldDeclaration(VariableDeclaration(ParseTypeName(field.Type))
                .AddVariables(VariableDeclarator(Identifier(field.Name))))
                .AddModifiers(Token(SyntaxKind.PrivateKeyword), Token(SyntaxKind.ReadOnlyKeyword));
            classDecl = classDecl.AddMembers(fieldDecl);
        }

        // Add Constructor
        if (fields.Any())
        {
            var parameters = fields.Select(f => Parameter(Identifier(f.Name.TrimStart('_'))).WithType(ParseTypeName(f.Type))).ToArray();
            var assignments = fields.Select(f => ExpressionStatement(
                AssignmentExpression(SyntaxKind.SimpleAssignmentExpression,
                    IdentifierName(f.Name),
                    IdentifierName(f.Name.TrimStart('_'))))).ToArray();

            var ctorDecl = ConstructorDeclaration(bp.ClassName ?? "GeneratedProcessor")
                .AddModifiers(Token(SyntaxKind.PublicKeyword))
                .WithParameterList(ParameterList(SeparatedList(parameters)))
                .WithBody(Block(assignments));
            classDecl = classDecl.AddMembers(ctorDecl);
        }

        // Add Methods
        foreach (var mbp in bp.Methods ?? new())
        {
            var retType = mbp.ReturnType ?? "void";
            if (mbp.IsAsync && !retType.StartsWith("Task")) retType = (retType == "void") ? "Task" : $"Task<{retType}>";
            var methodDecl = MethodDeclaration(ParseTypeName(retType), mbp.Name ?? "Execute").AddModifiers(Token(SyntaxKind.PublicKeyword));
            if (mbp.IsAsync) methodDecl = methodDecl.AddModifiers(Token(SyntaxKind.AsyncKeyword));
            
            // Add Parameters
            if (mbp.Params != null && mbp.Params.Count > 0)
            {
                var methodParams = mbp.Params.Select(p => Parameter(Identifier(p.Name)).WithType(ParseTypeName(p.Type))).ToArray();
                methodDecl = methodDecl.WithParameterList(ParameterList(SeparatedList(methodParams)));
            }

            var statements = (mbp.Body ?? new()).Select(s => ConvertStatement(s)).Where(s => s != null).ToList();
            classDecl = classDecl.AddMembers(methodDecl.WithBody(Block(statements)));
        }

        var members = new List<MemberDeclarationSyntax> { classDecl };
        foreach (var ec in bp.ExtraClasses ?? new())
        {
            var ecDecl = ClassDeclaration(ec.Name).AddModifiers(Token(SyntaxKind.PublicKeyword));
            foreach (var prop in ec.Properties ?? new())
            {
                var propDecl = PropertyDeclaration(ParseTypeName(prop.Type), prop.Name).AddModifiers(Token(SyntaxKind.PublicKeyword))
                    .AddAccessorListAccessors(AccessorDeclaration(SyntaxKind.GetAccessorDeclaration).WithSemicolonToken(Token(SyntaxKind.SemicolonToken)),
                                              AccessorDeclaration(SyntaxKind.SetAccessorDeclaration).WithSemicolonToken(Token(SyntaxKind.SemicolonToken)));
                
                if (prop.Attributes?.Count > 0)
                {
                    var attrList = AttributeList(SeparatedList(prop.Attributes.Select(a => Attribute(ParseName(a)))));
                    propDecl = propDecl.AddAttributeLists(attrList);
                }
                
                ecDecl = ecDecl.AddMembers(propDecl);
            }
            members.Add(ecDecl);
        }

        var namespaceDecl = NamespaceDeclaration(ParseName(bp.Namespace ?? "Generated")).AddMembers(members.ToArray());
        var compilationMembers = new List<MemberDeclarationSyntax> { namespaceDecl };
        var extraUsings = new List<UsingDirectiveSyntax>();
        foreach (var code in bp.ExtraCode ?? new())
        {
            if (string.IsNullOrWhiteSpace(code)) continue;
            var extraTree = CSharpSyntaxTree.ParseText(code);
            var extraRoot = extraTree.GetCompilationUnitRoot();
            if (extraRoot.Usings.Count > 0)
            {
                extraUsings.AddRange(extraRoot.Usings);
            }
            foreach (var m in extraRoot.Members)
            {
                compilationMembers.Add(m);
            }
        }
        var root = CompilationUnit().AddMembers(compilationMembers.ToArray());
        var usingList = new List<UsingDirectiveSyntax>();
        if (bp.Usings?.Count > 0) usingList.AddRange(bp.Usings.Distinct().Select(u => UsingDirective(ParseName(u))));
        if (extraUsings.Count > 0) usingList.AddRange(extraUsings);
        if (usingList.Count > 0) root = root.WithUsings(List(usingList.Distinct()));
        return root.NormalizeWhitespace().ToFullString();
    }

    static StatementSyntax ConvertStatement(StatementBlueprint s)
    {
        if (s == null || string.IsNullOrEmpty(s.Type)) return null;
        try {
            switch (s.Type.ToLower())
            {
                case "assign":
                    ExpressionSyntax assignVal;
                    try { assignVal = ParseExpression(s.Value); } 
                    catch { assignVal = IdentifierName($"/* Parse Error: {s.Value} */"); }
                    
                    if (s.VarType == null)
                    {
                        return LocalDeclarationStatement(VariableDeclaration(IdentifierName("var"))
                            .AddVariables(VariableDeclarator(Identifier(s.VarName)).WithInitializer(EqualsValueClause(assignVal))));
                    }
                    else if (s.VarType == "")
                    {
                        return ExpressionStatement(AssignmentExpression(SyntaxKind.SimpleAssignmentExpression, IdentifierName(s.VarName), assignVal));
                    }
                    else
                    {
                        return LocalDeclarationStatement(VariableDeclaration(ParseTypeName(s.VarType))
                            .AddVariables(VariableDeclarator(Identifier(s.VarName)).WithInitializer(EqualsValueClause(assignVal))));
                    }
                case "call":
                    ExpressionSyntax invoke;
                    try { invoke = ParseExpression(s.Method); }
                    catch { invoke = IdentifierName($"/* Parse Error in Method: {s.Method} */"); }

                    if (s.Args?.Count > 0) 
                    {
                        invoke = InvocationExpression(invoke).AddArgumentListArguments(s.Args.Select(a => {
                            try { return Argument(ParseExpression(a)); }
                            catch { return Argument(IdentifierName($"/* Parse Error in Arg: {a} */")); }
                        }).ToArray());
                    }
                    else if (!string.IsNullOrEmpty(s.Method) && !s.Method.Contains("(")) invoke = InvocationExpression(invoke); // Ensure it's a call
                    
                    if (s.IsAsync) invoke = AwaitExpression(invoke);
                    
                    if (!string.IsNullOrEmpty(s.OutVar))
                    {
                        if (s.VarType == null)
                        {
                            return LocalDeclarationStatement(VariableDeclaration(IdentifierName("var"))
                                .AddVariables(VariableDeclarator(Identifier(s.OutVar)).WithInitializer(EqualsValueClause(invoke))));
                        }
                        else if (s.VarType == "")
                        {
                            // Already declared, just an assignment
                            return ExpressionStatement(AssignmentExpression(SyntaxKind.SimpleAssignmentExpression, IdentifierName(s.OutVar), invoke));
                        }
                        else
                        {
                            return LocalDeclarationStatement(VariableDeclaration(ParseTypeName(s.VarType))
                                .AddVariables(VariableDeclarator(Identifier(s.OutVar)).WithInitializer(EqualsValueClause(invoke))));
                        }
                    }
                    return ExpressionStatement(invoke);
                case "if":
                    var ifStmt = IfStatement(ParseExpression(s.Condition), Block((s.Body ?? new()).Select(sub => ConvertStatement(sub)).Where(x => x != null)));
                    if (s.ElseBody != null && s.ElseBody.Count > 0)
                    {
                        ifStmt = ifStmt.WithElse(ElseClause(Block(s.ElseBody.Select(sub => ConvertStatement(sub)).Where(x => x != null))));
                    }
                    return ifStmt;
                case "foreach":
                    string src = !string.IsNullOrWhiteSpace(s.Source) ? s.Source : (!string.IsNullOrWhiteSpace(s.Collection) ? s.Collection : "items");
                    string item = !string.IsNullOrWhiteSpace(s.ItemName) ? s.ItemName : (!string.IsNullOrWhiteSpace(s.ItemVar) ? s.ItemVar : "item");
                    // Use var for foreach loop variable by default or if requested
                    TypeSyntax itemType = (string.IsNullOrEmpty(s.VarType) || s.VarType == "var") ? IdentifierName("var") : ParseTypeName(s.VarType);
                    return ForEachStatement(itemType, Identifier(item), ParseExpression(src), 
                        Block((s.Body ?? new()).Select(sub => ConvertStatement(sub)).Where(x => x != null)));
                case "while":
                    return WhileStatement(ParseExpression(s.Condition), Block((s.Body ?? new()).Select(sub => ConvertStatement(sub)).Where(x => x != null)));
                case "try":
                    var tryBlock = Block((s.Body ?? new()).Select(sub => ConvertStatement(sub)).Where(x => x != null));
                    var catchBlock = Block((s.ElseBody ?? new()).Select(sub => ConvertStatement(sub)).Where(x => x != null));
                    var catchClause = CatchClause().WithDeclaration(CatchDeclaration(ParseTypeName("Exception")).WithIdentifier(Identifier("ex"))).WithBlock(catchBlock);
                    return TryStatement().WithBlock(tryBlock).WithCatches(SingletonList(catchClause));
                case "raw":
                    string rawCode = !string.IsNullOrEmpty(s.Code) ? s.Code : s.Text;
                    if (string.IsNullOrWhiteSpace(rawCode)) return EmptyStatement();
                    rawCode = rawCode.Trim();
                    // 27.222: Only append semicolon if not a block or already semi-terminated
                    string suffix = (rawCode.EndsWith(";") || rawCode.EndsWith("}")) ? "\n" : ";\n";
                    return ParseStatement(rawCode + suffix);
                case "comment": 
                case "todo":
                    var msg = s.Text ?? s.Value ?? s.Method ?? "TODO";
                    return EmptyStatement().WithTrailingTrivia(Comment($"// {msg}\n"));
                default: 
                    return ParseStatement($"// TODO: Unsupported type '{s.Type}' - {s.Text}\n");
            }
        } catch (Exception ex) { return ParseStatement($"// Build Error in {s.Type}: {ex.Message}\n"); }
    }

    static string OptimizeCode(string code)
    {
        var tree = CSharpSyntaxTree.ParseText(code);
        var root = tree.GetCompilationUnitRoot();
        
        // 1. Find all used variables
        var walker = new VariableUsageWalker();
        walker.Visit(root);
        
        // 2. Remove unused local declarations
        var rewriter = new UnusedVariableRemover(walker.UsedNames);
        var newRoot = rewriter.Visit(root);
        
        return newRoot.NormalizeWhitespace().ToFullString();
    }
}

class VariableUsageWalker : CSharpSyntaxWalker
{
    public HashSet<string> UsedNames { get; } = new HashSet<string>();
    public override void VisitIdentifierName(IdentifierNameSyntax node)
    {
        UsedNames.Add(node.Identifier.ValueText);
        base.VisitIdentifierName(node);
    }
}

class UnusedVariableRemover : CSharpSyntaxRewriter
{
    private readonly HashSet<string> _usedNames;
    public UnusedVariableRemover(HashSet<string> usedNames) => _usedNames = usedNames;

    public override SyntaxNode? VisitLocalDeclarationStatement(LocalDeclarationStatementSyntax node)
    {
        var variables = node.Declaration.Variables;
        var remainingVariables = variables.Where(v => _usedNames.Contains(v.Identifier.ValueText)).ToList();
        
        if (remainingVariables.Count == 0) return null; // Entire statement removed
        
        if (remainingVariables.Count < variables.Count)
        {
            return node.WithDeclaration(node.Declaration.WithVariables(SeparatedList(remainingVariables)));
        }
        return base.VisitLocalDeclarationStatement(node);
    }
}
