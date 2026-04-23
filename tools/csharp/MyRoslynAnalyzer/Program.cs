using Microsoft.Build.Locator;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.MSBuild;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Diagnostics; // Added for Process
using System.Text.RegularExpressions; // Added for wildcard matching
using System.Threading.Tasks;
using System.Xml.Linq;

namespace MyRoslynAnalyzer
{
    #region Data Models
    public record Documentation(
        [property: JsonPropertyName("summary")] string Summary,
        [property: JsonPropertyName("remarks")] string Remarks,
        [property: JsonPropertyName("params")] Dictionary<string, string> Params
    );

    public class Metrics
    {
        [JsonPropertyName("cyclomaticComplexity")] public int CyclomaticComplexity { get; set; }
        [JsonPropertyName("lineCount")] public int LineCount { get; set; }
        [JsonPropertyName("bodyHash")] public string BodyHash { get; set; }
        [JsonPropertyName("maxComplexity")] public int MaxComplexity { get; set; }

        public Metrics(int cc, int lc, string hash, int maxCc = 0)
        {
            CyclomaticComplexity = cc;
            LineCount = lc;
            BodyHash = hash;
            MaxComplexity = maxCc;
        }
    }

    public record DependencyInfo(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("filePath")] string FilePath,
        [property: JsonPropertyName("line")] int Line
    );

    public record ParameterInfo(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("type")] string Type
    );

    public record BranchInfo(
        [property: JsonPropertyName("type")] string Type, // "If", "Switch", "While", etc.
        [property: JsonPropertyName("condition")] string Condition,
        [property: JsonPropertyName("line")] int Line
    );

    public record ConstructorInfo(
        [property: JsonPropertyName("accessibility")] string Accessibility,
        [property: JsonPropertyName("parameters")] List<ParameterInfo> Parameters
    );

    public record CodeProperty(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("type")] string Type,
        [property: JsonPropertyName("accessibility")] string Accessibility,
        [property: JsonPropertyName("modifiers")] List<string> Modifiers, // New
        [property: JsonPropertyName("startLine")] int StartLine,
        [property: JsonPropertyName("endLine")] int EndLine, 
        [property: JsonPropertyName("accessedBy")] List<DependencyInfo> AccessedBy,
        [property: JsonPropertyName("isField")] bool IsField 
    );

    public class CodeMethod
    {
        [JsonPropertyName("id")] public string Id { get; init; }
        [JsonPropertyName("name")] public string Name { get; init; }
        [JsonPropertyName("returnType")] public string ReturnType { get; init; }
        [JsonPropertyName("accessibility")] public string Accessibility { get; init; }
        [JsonPropertyName("modifiers")] public List<string> Modifiers { get; init; } // New
        [JsonPropertyName("startLine")] public int StartLine { get; init; }
        [JsonPropertyName("endLine")] public int EndLine { get; init; }
        [JsonPropertyName("bodyCode")] public string BodyCode { get; init; } // New
        [JsonPropertyName("documentation")] public Documentation Documentation { get; init; }
        [JsonPropertyName("parameters")] public List<ParameterInfo> Parameters { get; init; }
        [JsonPropertyName("branches")] public List<BranchInfo> Branches { get; init; } // New
        [JsonPropertyName("metrics")] public Metrics Metrics { get; set; }
        [JsonPropertyName("calls")] public List<DependencyInfo> Calls { get; init; }
        [JsonPropertyName("calledBy")] public List<DependencyInfo> CalledBy { get; init; }
        [JsonPropertyName("accesses")] public List<DependencyInfo> Accesses { get; init; }

        public CodeMethod(string id, string name, string returnType, string accessibility, List<string> modifiers, int startLine, int endLine, string bodyCode, Documentation documentation, List<ParameterInfo> parameters, List<BranchInfo> branches, Metrics metrics, List<DependencyInfo> calls, List<DependencyInfo> calledBy, List<DependencyInfo> accesses)
        {
            Id = id;
            Name = name;
            ReturnType = returnType;
            Accessibility = accessibility;
            Modifiers = modifiers;
            StartLine = startLine;
            EndLine = endLine;
            BodyCode = bodyCode;
            Documentation = documentation;
            Parameters = parameters;
            Branches = branches;
            Metrics = metrics;
            Calls = calls;
            CalledBy = calledBy;
            Accesses = accesses;
        }
    }

    public class CodeObject
    {
        [JsonPropertyName("id")] public string Id { get; init; }
        [JsonPropertyName("fullName")] public string FullName { get; init; }
        [JsonPropertyName("type")] public string Type { get; init; }
        [JsonPropertyName("baseType")] public string BaseType { get; init; }
        [JsonPropertyName("accessibility")] public string Accessibility { get; init; }
        [JsonPropertyName("modifiers")] public List<string> Modifiers { get; init; } // New
        [JsonPropertyName("startLine")] public int StartLine { get; init; }
        [JsonPropertyName("endLine")] public int EndLine { get; init; }
        [JsonPropertyName("filePath")] public string FilePath { get; init; }
        [JsonPropertyName("usings")] public List<string> Usings { get; init; } // New
        [JsonPropertyName("documentation")] public Documentation Documentation { get; init; }
        [JsonPropertyName("metrics")] public Metrics Metrics { get; set; }
        [JsonPropertyName("properties")] public List<CodeProperty> Properties { get; init; }
        [JsonPropertyName("methods")] public List<CodeMethod> Methods { get; init; }
        [JsonPropertyName("constructors")] public List<ConstructorInfo> Constructors { get; init; } // New
        [JsonPropertyName("dependencies")] public List<DependencyInfo> Dependencies { get; init; }

        public CodeObject(string id, string fullName, string type, string baseType, string accessibility, List<string> modifiers, int startLine, int endLine, string filePath, List<string> usings, Documentation documentation, Metrics metrics, List<CodeProperty> properties, List<CodeMethod> methods, List<ConstructorInfo> constructors, List<DependencyInfo> dependencies)
        {
            Id = id;
            FullName = fullName;
            Type = type;
            BaseType = baseType;
            Accessibility = accessibility;
            Modifiers = modifiers;
            StartLine = startLine;
            EndLine = endLine;
            FilePath = filePath;
            Usings = usings;
            Documentation = documentation;
            Metrics = metrics;
            Properties = properties;
            Methods = methods;
            Constructors = constructors;
            Dependencies = dependencies;
        }
    }

    public record ManifestObject(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("fullName")] string FullName,
        [property: JsonPropertyName("type")] string Type, // Changed to string
        [property: JsonPropertyName("filePath")] string FilePath,
        [property: JsonPropertyName("startLine")] int StartLine, // New
        [property: JsonPropertyName("endLine")] int EndLine, // New
        [property: JsonPropertyName("summary")] string Summary
    );

    public record ProjectMetrics(
        [property: JsonPropertyName("totalCyclomaticComplexity")] int TotalCyclomaticComplexity,
        [property: JsonPropertyName("maxCyclomaticComplexity")] int MaxCyclomaticComplexity,
        [property: JsonPropertyName("averageCyclomaticComplexity")] double AverageCyclomaticComplexity,
        [property: JsonPropertyName("totalLineCount")] int TotalLineCount
    );

    public record Manifest(
        [property: JsonPropertyName("projectName")] string ProjectName,
        [property: JsonPropertyName("assemblies")] List<string?> Assemblies,
        [property: JsonPropertyName("objects")] List<ManifestObject> Objects,
        [property: JsonPropertyName("projectMetrics")] ProjectMetrics ProjectMetrics // New
    );
    #endregion

    #region Analysis Walkers
    class DefinitionWalker : CSharpSyntaxWalker
    {
        private readonly SemanticModel _semanticModel;
        public readonly Dictionary<string, CodeObject> CodeObjects = new();

        private static readonly SymbolDisplayFormat FullyQualifiedFormat = new SymbolDisplayFormat(
            typeQualificationStyle: SymbolDisplayTypeQualificationStyle.NameAndContainingTypesAndNamespaces,
            genericsOptions: SymbolDisplayGenericsOptions.IncludeTypeParameters,
            miscellaneousOptions: SymbolDisplayMiscellaneousOptions.None // Important: ensures System.String instead of string
        );

        public DefinitionWalker(SemanticModel semanticModel)
        {
            _semanticModel = semanticModel;
        }

        private List<string> GetModifiers(ISymbol symbol)
        {
            var modifiers = new List<string>();
            if (symbol.IsStatic) modifiers.Add("static");
            if (symbol.IsAbstract) modifiers.Add("abstract");
            if (symbol.IsSealed) modifiers.Add("sealed");
            if (symbol.IsVirtual) modifiers.Add("virtual");
            if (symbol.IsOverride) modifiers.Add("override");
            return modifiers;
        }

        private void AddTypeDeclaration(BaseTypeDeclarationSyntax node, string typeKind)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node);
            if (symbol != null)
            {
                var id = GetUniqueId(symbol);
                if (!CodeObjects.ContainsKey(id))
                {
                    var doc = ParseDocumentation(symbol);
                    var constructors = symbol.InstanceConstructors.Select(c => new ConstructorInfo(
                        c.DeclaredAccessibility.ToString(),
                        c.Parameters.Select(p => new ParameterInfo(p.Name, p.Type.ToDisplayString(FullyQualifiedFormat))).ToList()
                    )).ToList();

                    var usings = node.SyntaxTree.GetRoot().DescendantNodes()
                        .OfType<UsingDirectiveSyntax>()
                        .Select(u => u.ToString().TrimEnd(';'))
                        .ToList();

                    CodeObjects[id] = new CodeObject(
                        id: id,
                        fullName: symbol.ToDisplayString(),
                        type: typeKind,
                        baseType: symbol.BaseType?.ToDisplayString(FullyQualifiedFormat) ?? string.Empty,
                        accessibility: symbol.DeclaredAccessibility.ToString(),
                        modifiers: GetModifiers(symbol),
                        startLine: node.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                        endLine: node.GetLocation().GetLineSpan().EndLinePosition.Line + 1,
                        filePath: node.SyntaxTree.FilePath,
                        usings: usings,
                        documentation: doc,
                        metrics: new Metrics(0, 0, string.Empty),
                        properties: new List<CodeProperty>(),
                        methods: new List<CodeMethod>(),
                        constructors: constructors,
                        dependencies: new List<DependencyInfo>()
                    );
                }
            }
        }

        public override void VisitClassDeclaration(ClassDeclarationSyntax node)
        {
            AddTypeDeclaration(node, "Class");
            base.VisitClassDeclaration(node);
        }

        public override void VisitRecordDeclaration(RecordDeclarationSyntax node)
        {
            AddTypeDeclaration(node, "Record");
            base.VisitRecordDeclaration(node);
        }

        public override void VisitStructDeclaration(StructDeclarationSyntax node)
        {
            AddTypeDeclaration(node, "Struct");
            base.VisitStructDeclaration(node);
        }

        public override void VisitInterfaceDeclaration(InterfaceDeclarationSyntax node)
        {
            AddTypeDeclaration(node, "Interface");
            base.VisitInterfaceDeclaration(node);
        }

        public override void VisitMethodDeclaration(MethodDeclarationSyntax node)
        {
            var methodSymbol = _semanticModel.GetDeclaredSymbol(node);
            var classSymbol = methodSymbol?.ContainingType;
            if (methodSymbol != null && classSymbol != null)
            {
                var classId = GetUniqueId(classSymbol);
                if (CodeObjects.TryGetValue(classId, out var codeObject))
                {
                    var methodId = GetUniqueId(methodSymbol);
                    var doc = ParseDocumentation(methodSymbol);

                    // Calculate metrics
                    var cyclomaticComplexity = CalculateCyclomaticComplexity(node);
                    var lineCount = node.GetLocation().GetLineSpan().EndLinePosition.Line - node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                    var bodyHash = CalculateBodyHash(node);
                    var branches = ExtractBranches(node);

                    var metrics = new Metrics(cyclomaticComplexity, lineCount, bodyHash);
                    var bodyCode = node.ToFullString();

                    var method = new CodeMethod(
                        id: methodId,
                        name: methodSymbol.Name,
                        returnType: methodSymbol.ReturnType.ToDisplayString(FullyQualifiedFormat),
                        accessibility: methodSymbol.DeclaredAccessibility.ToString(),
                        modifiers: GetModifiers(methodSymbol),
                        startLine: node.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                        endLine: node.GetLocation().GetLineSpan().EndLinePosition.Line + 1,
                        bodyCode: bodyCode,
                        documentation: doc,
                        parameters: methodSymbol.Parameters.Select(p => new ParameterInfo(p.Name, p.Type.ToDisplayString(FullyQualifiedFormat))).ToList(),
                        branches: branches,
                        metrics: metrics,
                        calls: new List<DependencyInfo>(),
                        calledBy: new List<DependencyInfo>(),
                        accesses: new List<DependencyInfo>()
                    );
                    if (!codeObject.Methods.Any(m => m.Id == methodId))
                        codeObject.Methods.Add(method);
                }
            }
            base.VisitMethodDeclaration(node);
        }

        public override void VisitPropertyDeclaration(PropertyDeclarationSyntax node)
        {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
            var propertySymbol = _semanticModel.GetDeclaredSymbol(node);
            var classSymbol = propertySymbol?.ContainingType;
            if (propertySymbol != null && classSymbol != null)
            {
                var classId = GetUniqueId(classSymbol);
                if (CodeObjects.TryGetValue(classId, out var codeObject))
                {
                    var property = new CodeProperty(
                        Id: GetUniqueId(propertySymbol),
                        Name: propertySymbol.Name,
                        Type: propertySymbol.Type.ToDisplayString(FullyQualifiedFormat),
                        Accessibility: propertySymbol.DeclaredAccessibility.ToString(),
                        Modifiers: GetModifiers(propertySymbol),
                        StartLine: node.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                        EndLine: node.GetLocation().GetLineSpan().EndLinePosition.Line + 1,
                        AccessedBy: new List<DependencyInfo>(),
                        IsField: false
                    );
                    if (!codeObject.Properties.Any(p => p.Id == property.Id))
                        codeObject.Properties.Add(property);
                }
            }
            base.VisitPropertyDeclaration(node);
        }

        public override void VisitFieldDeclaration(FieldDeclarationSyntax node)
        {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
            foreach (var variable in node.Declaration.Variables)
            {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                var fieldSymbol = _semanticModel.GetDeclaredSymbol(variable) as IFieldSymbol;
                var classSymbol = fieldSymbol?.ContainingType;
                if (fieldSymbol != null && classSymbol != null)
                {
                    var classId = GetUniqueId(classSymbol);
                    if (CodeObjects.TryGetValue(classId, out var codeObject))
                    {
                        var field = new CodeProperty(
                            Id: GetUniqueId(fieldSymbol),
                            Name: fieldSymbol.Name,
                            Type: fieldSymbol.Type.ToDisplayString(FullyQualifiedFormat),
                            Accessibility: fieldSymbol.DeclaredAccessibility.ToString(),
                            Modifiers: GetModifiers(fieldSymbol),
                            StartLine: node.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                            EndLine: node.GetLocation().GetLineSpan().EndLinePosition.Line + 1,
                            AccessedBy: new List<DependencyInfo>(),
                            IsField: true
                        );
                        if (!codeObject.Properties.Any(p => p.Id == field.Id))
                            codeObject.Properties.Add(field);
                    }
                }
            }
            base.VisitFieldDeclaration(node);
        }
        public static string GetUniqueId(ISymbol symbol)
        {
            using var sha256 = SHA256.Create();
            var hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(symbol.ToDisplayString()));
            return Convert.ToBase64String(hash).Replace("/", "_").Replace("+", "-").Substring(0, 10);
        }

        private static Documentation ParseDocumentation(ISymbol symbol)
        {
            var xml = symbol.GetDocumentationCommentXml();
            if (string.IsNullOrEmpty(xml)) return new Documentation("", "", new Dictionary<string, string>());
            var xdoc = XElement.Parse(xml);
            var summary = string.Join("\n", xdoc.Element("summary")?.Value.Split('\n').Select(line => line.Trim()) ?? new string[] { "" });
            var remarks = string.Join("\n", xdoc.Element("remarks")?.Value.Split('\n').Select(line => line.Trim()) ?? new string[] { "" });
            var parms = xdoc.Elements("param").ToDictionary(p => p.Attribute("name")?.Value ?? "", p => p.Value.Trim());
            return new Documentation(summary, remarks, parms);
        }

        private static List<BranchInfo> ExtractBranches(MethodDeclarationSyntax method)
        {
            var branches = new List<BranchInfo>();

            foreach (var ifStmt in method.DescendantNodes().OfType<IfStatementSyntax>())
            {
                branches.Add(new BranchInfo("If", ifStmt.Condition.ToString(), ifStmt.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            foreach (var switchStmt in method.DescendantNodes().OfType<SwitchStatementSyntax>())
            {
                branches.Add(new BranchInfo("Switch", switchStmt.Expression.ToString(), switchStmt.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            foreach (var whileStmt in method.DescendantNodes().OfType<WhileStatementSyntax>())
            {
                branches.Add(new BranchInfo("While", whileStmt.Condition.ToString(), whileStmt.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            foreach (var forStmt in method.DescendantNodes().OfType<ForStatementSyntax>())
            {
                branches.Add(new BranchInfo("For", forStmt.Condition?.ToString() ?? "", forStmt.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            foreach (var foreachStmt in method.DescendantNodes().OfType<ForEachStatementSyntax>())
            {
                branches.Add(new BranchInfo("ForEach", foreachStmt.Expression.ToString(), foreachStmt.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            foreach (var ternary in method.DescendantNodes().OfType<ConditionalExpressionSyntax>())
            {
                branches.Add(new BranchInfo("Ternary", ternary.Condition.ToString(), ternary.GetLocation().GetLineSpan().StartLinePosition.Line + 1));
            }

            return branches;
        }

        private static int CalculateCyclomaticComplexity(MethodDeclarationSyntax method)
        {
            // Start with 1 for the method entry
            var complexity = 1;

            // Increment for each control flow statement
            complexity += method.DescendantNodes().OfType<IfStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<ForStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<ForEachStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<WhileStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<DoStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<SwitchStatementSyntax>().Count();
            complexity += method.DescendantNodes().OfType<CasePatternSwitchLabelSyntax>().Count(); // For switch expressions
            complexity += method.DescendantNodes().OfType<CatchClauseSyntax>().Count();
            complexity += method.DescendantNodes().OfType<ConditionalExpressionSyntax>().Count(); // Ternary operator

            // Logical operators (&&, ||)
            complexity += method.DescendantNodes().OfType<BinaryExpressionSyntax>()
                                .Count(b => b.Kind() == SyntaxKind.LogicalAndExpression || b.Kind() == SyntaxKind.LogicalOrExpression);

            return complexity;
        }

        private static string CalculateBodyHash(MethodDeclarationSyntax method)
        {
            if (method.Body != null)
            {
                using var sha256 = SHA256.Create();
                var hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(method.Body.ToFullString()));
                return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
            if (method.ExpressionBody != null)
            {
                using var sha256 = SHA256.Create();
                var hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(method.ExpressionBody.ToFullString()));
                return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
            return string.Empty;
        }
    }

    class DependencyWalker : CSharpSyntaxWalker
    {
        private readonly SemanticModel _semanticModel;
        private readonly CodeMethod _currentMethod;

        public DependencyWalker(SemanticModel semanticModel, CodeMethod currentMethod)
        {
            _semanticModel = semanticModel;
            _currentMethod = currentMethod;
        }

        private void AddDependency(ISymbol symbol, SyntaxNode node, List<DependencyInfo> collection)
        {
            if (symbol != null)
            {
                var id = DefinitionWalker.GetUniqueId(symbol);
                var filePath = node.SyntaxTree.FilePath;
                var line = node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                collection.Add(new DependencyInfo(id, filePath, line));
            }
        }

        public override void VisitInvocationExpression(InvocationExpressionSyntax node)
        {
            var symbolInfo = _semanticModel.GetSymbolInfo(node);
            if (symbolInfo.Symbol is IMethodSymbol symbol)
            {
                AddDependency(symbol, node, _currentMethod.Calls);
            }
            base.VisitInvocationExpression(node);
        }

        public override void VisitMemberAccessExpression(MemberAccessExpressionSyntax node)
        {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
            var symbolInfo = _semanticModel.GetSymbolInfo(node.Name);
            if (symbolInfo.Symbol is IPropertySymbol propertySymbol)
            {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                AddDependency(propertySymbol, node, _currentMethod.Accesses);
            }
            else if (symbolInfo.Symbol is IFieldSymbol fieldSymbol)
            {
                AddDependency(fieldSymbol, node, _currentMethod.Accesses);
            }
            base.VisitMemberAccessExpression(node);
        }

        public override void VisitAssignmentExpression(AssignmentExpressionSyntax node)
        {
            var symbolInfo = _semanticModel.GetSymbolInfo(node.Left);
            if (symbolInfo.Symbol is IPropertySymbol propertySymbol)
            {
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                if (node == null) throw new ArgumentNullException(nameof(node));
                AddDependency(propertySymbol, node, _currentMethod.Accesses);
            }
            else if (symbolInfo.Symbol is IFieldSymbol fieldSymbol)
            {
                AddDependency(fieldSymbol, node, _currentMethod.Accesses);
            }
            base.VisitAssignmentExpression(node);
        }
    }
    #endregion

    public static class WildcardMatcher
    {
        public static bool Matches(string input, string pattern)
        {
            if (string.IsNullOrEmpty(pattern))
            {
                return false; // No pattern, so nothing is excluded.
            }

            // Convert DOS-like wildcards (*, ?) to regex
            string regexPattern = "^" + System.Text.RegularExpressions.Regex.Escape(pattern).Replace("\\*", ".*").Replace("\\?", ".") + "$";
            return System.Text.RegularExpressions.Regex.IsMatch(input, regexPattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        }
    }

    public record Config(
        [property: JsonPropertyName("fileSuffixes")] List<string> FileSuffixes,
        [property: JsonPropertyName("namespaces")] List<string> Namespaces
    );

    class Program
    {
        static async Task<int> Main(string[] args)
        {
            if (args.Length < 2)
            {
                Console.Error.WriteLine("Usage: MyRoslynAnalyzer.exe <input_path> <output_path> [--exclude <pattern>]");
                return 1;
            }

            string inputPath = args[0];
            string outputPath = args[1];
            string excludePattern = null;

            for (int i = 2; i < args.Length; i++)
            {
                if (args[i].Equals("--exclude", StringComparison.OrdinalIgnoreCase))
                {
                    if (i + 1 < args.Length)
                    {
                        excludePattern = args[i + 1];
                        i++; // Skip the pattern
                    }
                    else
                    {
                        Console.Error.WriteLine("Error: --exclude option requires a pattern.");
                        return 1;
                    }
                }
            }

            // Load config.json if it exists (assuming it's in the current directory or same dir as executable)
            Config config = new Config(new List<string>(), new List<string>());
            string exePath = Path.GetDirectoryName(Process.GetCurrentProcess().MainModule.FileName);
            string configPath = Path.Combine(exePath, "config.json");
            
            // Also check current directory
            if (!File.Exists(configPath))
            {
                 configPath = "config.json";
            }

            if (File.Exists(configPath))
            {
                try
                {
                    var json = await File.ReadAllTextAsync(configPath);
                    var loadedConfig = JsonSerializer.Deserialize<Config>(json);
                    if (loadedConfig != null)
                    {
                        config = loadedConfig;
                        Console.WriteLine($"Loaded configuration from {configPath}");
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"Warning: Failed to load config.json: {ex.Message}");
                }
            }

            if (!MSBuildLocator.IsRegistered)
            {
                var instances = MSBuildLocator.QueryVisualStudioInstances().ToArray();
                if (!instances.Any())
                {
                    Console.Error.WriteLine("No MSBuild instances found.");
                    return 1;
                }
                MSBuildLocator.RegisterInstance(instances.OrderByDescending(x => x.Version).First());
            }

            Console.WriteLine($"Starting analysis of '{inputPath}'...");
            using var workspace = MSBuildWorkspace.Create();
            Solution solution = null;
            Project projectToAnalyze = null;

            if (File.Exists(inputPath))
            {
                // Assume it's a solution or project file
                if (inputPath.EndsWith(".sln", StringComparison.OrdinalIgnoreCase))
                {
                    solution = await workspace.OpenSolutionAsync(inputPath);
                }
                else if (inputPath.EndsWith(".csproj", StringComparison.OrdinalIgnoreCase))
                {
                    projectToAnalyze = await workspace.OpenProjectAsync(inputPath);
                    solution = projectToAnalyze.Solution; // Get the solution context from the project
                }
                else
                {
                    Console.Error.WriteLine($"Error: Unsupported input file type: {inputPath}");
                    return 1;
                }
            }
            else if (Directory.Exists(inputPath))
            {
                // Search for .sln or .csproj within the directory
                var slnFiles = Directory.EnumerateFiles(inputPath, "*.sln", SearchOption.TopDirectoryOnly).ToList();
                var csprojFiles = Directory.EnumerateFiles(inputPath, "*.csproj", SearchOption.TopDirectoryOnly).ToList();

                if (slnFiles.Any())
                {
                    solution = await workspace.OpenSolutionAsync(slnFiles.First());
                }
                else if (csprojFiles.Any())
                {
                    projectToAnalyze = await workspace.OpenProjectAsync(csprojFiles.First());
                    solution = projectToAnalyze.Solution;
                }
                else
                {
                    Console.Error.WriteLine($"Error: No solution (.sln) or project (.csproj) file found in the directory: {inputPath}");
                    return 1;
                }
            }
            else
            {
                Console.Error.WriteLine($"Error: Input path '{inputPath}' does not exist or is not a valid file/directory.");
                return 1;
            }

            if (solution == null && projectToAnalyze == null)
            {
                Console.Error.WriteLine("Error: Failed to load solution or project.");
                return 1;
            }
            
            var allObjects = new Dictionary<string, CodeObject>();
            var methodSyntaxNodes = new Dictionary<string, (MethodDeclarationSyntax Node, Compilation Compilation)>();
            var assemblyNames = new List<string?>(); // To store assembly names, allowing for nulls if compilation.AssemblyName is null

            // Pass 1: Definitions
            Console.WriteLine("Pass 1: Extracting definitions...");
            IEnumerable<Project> projectsToProcess = projectToAnalyze != null ? new[] { projectToAnalyze } : solution.Projects;

            foreach (var project in projectsToProcess)
            {
                var compilation = await project.GetCompilationAsync();
                if (compilation == null) continue;
                if (compilation.AssemblyName != null) // Add null check
                {
                    assemblyNames.Add(compilation.AssemblyName); // Add assembly name
                }

                foreach (var tree in compilation.SyntaxTrees)
                {
                    // Filter by --exclude pattern
                    if (!string.IsNullOrEmpty(excludePattern) && WildcardMatcher.Matches(tree.FilePath, excludePattern))
                    {
                        Console.WriteLine($"Skipping excluded file (CLI pattern): {tree.FilePath}");
                        continue;
                    }

                    // Filter by config.fileSuffixes
                    if (config.FileSuffixes != null && config.FileSuffixes.Any(suffix => tree.FilePath.EndsWith(suffix, StringComparison.OrdinalIgnoreCase)))
                    {
                         Console.WriteLine($"Skipping excluded file (config suffix): {tree.FilePath}");
                         continue;
                    }

                    var semanticModel = compilation.GetSemanticModel(tree);
                    var root = await tree.GetRootAsync();
                    var walker = new DefinitionWalker(semanticModel);
                    walker.Visit(root);
                    
                    foreach(var (id, obj) in walker.CodeObjects)
                    {
                        // Filter by config.namespaces
                        // obj.FullName usually contains the namespace. 
                        // We check if the FullName starts with any of the ignored namespaces.
                        // Ideally we should check the symbol's namespace, but obj.FullName is a good proxy if symbols are fully qualified.
                        // Or we can check if the object Type is derived from a symbol in an ignored namespace (harder).
                        // Simple check:
                        if (config.Namespaces != null && config.Namespaces.Any(ns => obj.FullName.StartsWith(ns + ".") || obj.FullName == ns))
                        {
                            // Skip this object
                            continue;
                        }

                        if (!allObjects.ContainsKey(id))
                        {
                            allObjects[id] = obj;
                        }

                        // Find and cache method syntax nodes for the next pass
                        foreach(var methodDecl in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
                        {
                            var methodSymbol = semanticModel.GetDeclaredSymbol(methodDecl);
                            if(methodSymbol != null)
                            {
                                // Apply namespace filter to methods too if needed, but methods are usually inside classes which are already filtered.
                                // However, we should be consistent. Methods in 'allObjects' come from 'walker.CodeObjects'.
                                // So we only need to worry about the cache here.
                                // If the class is skipped, we likely won't process its methods in the walker loop above?
                                // Wait, DefinitionWalker visits ALL nodes.
                                // But here we are iterating 'walker.CodeObjects' which contains Classes.
                                // Methods are inside CodeObject.Methods.
                                // So if we skip the CodeObject (Class), we implicitly skip its methods for the final output.
                                // BUT methodSyntaxNodes is used for Pass 2 (Dependencies).
                                // If we don't filter methodSyntaxNodes, Pass 2 might try to analyze methods of ignored classes.
                                // That's probably fine, or we can filter here too.
                                
                                // Let's check the containing type of the method to be safe.
                                var containingType = methodSymbol.ContainingType;
                                if (containingType != null)
                                {
                                     string typeFullName = containingType.ToDisplayString();
                                     if (config.Namespaces != null && config.Namespaces.Any(ns => typeFullName.StartsWith(ns + ".") || typeFullName == ns))
                                     {
                                         continue;
                                     }
                                }

                                var methodId = DefinitionWalker.GetUniqueId(methodSymbol);
                                if (!methodSyntaxNodes.ContainsKey(methodId))
                                {
                                     methodSyntaxNodes[methodId] = (methodDecl, compilation);
                                }
                            }
                        }
                    }
                }
            }

            // Pass 2: Dependencies
            Console.WriteLine("Pass 2: Analyzing dependencies...");
            foreach (var codeObject in allObjects.Values)
            {
                foreach (var method in codeObject.Methods)
                {
                    if (methodSyntaxNodes.TryGetValue(method.Id, out var methodInfo))
                    {
                        var semanticModel = methodInfo.Compilation.GetSemanticModel(methodInfo.Node.SyntaxTree);
                        var dependencyWalker = new DependencyWalker(semanticModel, method);
                        // Visit the entire method node, not just the body, to catch member accesses in initializers etc.
                        dependencyWalker.Visit(methodInfo.Node);
                    }
                }
            }

            // Pass 3: Building inverse relationships and class-level dependencies
            Console.WriteLine("Pass 3: Building inverse relationships and class-level dependencies/metrics...");

            var methodsById = allObjects.Values.SelectMany(o => o.Methods).ToDictionary(m => m.Id);
            var propertiesById = allObjects.Values.SelectMany(o => o.Properties).ToDictionary(p => p.Id);

            foreach (var callingMethod in methodsById.Values)
            {
                // Populate CalledBy for methods
                foreach (var calledDependencyInfo in callingMethod.Calls)
                {
                    if (methodsById.TryGetValue(calledDependencyInfo.Id, out var calledMethod))
                    {
                        // Add calling method's info to the called method's CalledBy list
                        calledMethod.CalledBy.Add(new DependencyInfo(
                            callingMethod.Id,
                            allObjects.Values.FirstOrDefault(o => o.Methods.Contains(callingMethod))?.FilePath ?? string.Empty,
                            calledDependencyInfo.Line // This line refers to the line where the call occurs
                        ));
                    }
                }

                // Populate AccessedBy for properties
                foreach (var accessedDependencyInfo in callingMethod.Accesses)
                {
                    if (propertiesById.TryGetValue(accessedDependencyInfo.Id, out var accessedProperty))
                    {
                        // Add calling method's info to the accessed property's AccessedBy list
                        accessedProperty.AccessedBy.Add(new DependencyInfo(
                            callingMethod.Id,
                            allObjects.Values.FirstOrDefault(o => o.Methods.Contains(callingMethod))?.FilePath ?? string.Empty,
                            accessedDependencyInfo.Line // This line refers to the line where the access occurs
                        ));
                    }
                }
            }

            // Populate class-level dependencies and metrics
            foreach (var codeObject in allObjects.Values)
            {
                if (codeObject.Type == "Class")
                {
                    var classDependencies = new HashSet<string>();
                    
                    // 1. Method call based dependencies
                    foreach (var method in codeObject.Methods)
                    {
                        foreach (var call in method.Calls)
                        {
                            if (methodsById.TryGetValue(call.Id, out var calledMethod))
                            {
                                var calledMethodContainingClass = allObjects.Values.FirstOrDefault(o => o.Methods.Contains(calledMethod));
                                if (calledMethodContainingClass != null && calledMethodContainingClass.Id != codeObject.Id)
                                {
                                    classDependencies.Add(calledMethodContainingClass.Id);
                                }
                            }
                        }
                    }

                    // 2. Base type dependency
                    if (!string.IsNullOrEmpty(codeObject.BaseType))
                    {
                        var baseObject = allObjects.Values.FirstOrDefault(o => o.FullName == codeObject.BaseType || o.FullName.EndsWith("." + codeObject.BaseType));
                        if (baseObject != null && baseObject.Id != codeObject.Id)
                        {
                            classDependencies.Add(baseObject.Id);
                        }
                    }

                    // 3. Property/Field type dependency
                    foreach (var prop in codeObject.Properties)
                    {
                        var typeObject = allObjects.Values.FirstOrDefault(o => o.FullName == prop.Type || o.FullName.EndsWith("." + prop.Type));
                        if (typeObject != null && typeObject.Id != codeObject.Id)
                        {
                            classDependencies.Add(typeObject.Id);
                        }
                    }

                    // Convert to DependencyInfo
                    foreach (var depId in classDependencies)
                    {
                        var depObject = allObjects[depId];
                        if (!codeObject.Dependencies.Any(d => d.Id == depId))
                        {
                            codeObject.Dependencies.Add(new DependencyInfo(depId, depObject.FilePath, depObject.StartLine));
                        }
                    }

                    // Aggregating Metrics
                    int totalCC = codeObject.Methods.Sum(m => m.Metrics.CyclomaticComplexity);
                    int maxCC = codeObject.Methods.Any() ? codeObject.Methods.Max(m => m.Metrics.CyclomaticComplexity) : 0;
                    int lineCount = codeObject.EndLine - codeObject.StartLine + 1;
                    
                    codeObject.Metrics = new Metrics(totalCC, lineCount, string.Empty, maxCC);
                }
            }

            // File Output
            Console.WriteLine("Writing output files...");

            // Calculate Project-level Metrics
            int projectTotalCyclomaticComplexity = allObjects.Values.SelectMany(o => o.Methods).Sum(m => m.Metrics.CyclomaticComplexity);
            int projectMaxCyclomaticComplexity = allObjects.Values.SelectMany(o => o.Methods).Any() ?
                allObjects.Values.SelectMany(o => o.Methods).Max(m => m.Metrics.CyclomaticComplexity) : 0;
            int projectTotalMethodCount = allObjects.Values.SelectMany(o => o.Methods).Count();
            double projectAverageCyclomaticComplexity = projectTotalMethodCount > 0 ?
                (double)projectTotalCyclomaticComplexity / projectTotalMethodCount : 0.0;
            int projectTotalLineCount = allObjects.Values.Sum(o => o.EndLine - o.StartLine + 1);

            var projectMetrics = new ProjectMetrics(
                TotalCyclomaticComplexity: projectTotalCyclomaticComplexity,
                MaxCyclomaticComplexity: projectMaxCyclomaticComplexity,
                AverageCyclomaticComplexity: projectAverageCyclomaticComplexity,
                TotalLineCount: projectTotalLineCount
            );

            var manifestObjects = allObjects.Values.Select(obj => new ManifestObject(
                Id: obj.Id, 
                FullName: obj.FullName, 
                Type: obj.Type, 
                FilePath: obj.FilePath, 
                StartLine: obj.StartLine, 
                EndLine: obj.EndLine, 
                Summary: obj.Documentation.Summary
            )).ToList();
            var manifest = new Manifest(
                ProjectName: projectToAnalyze?.Name ?? Path.GetFileNameWithoutExtension(solution.FilePath ?? "Solution"),
                Assemblies: assemblyNames,
                Objects: manifestObjects,
                ProjectMetrics: projectMetrics // Pass the calculated project metrics
            );
            
            Directory.CreateDirectory(Path.Combine(outputPath, "details"));
            var serializerOptions = new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };
            
            await File.WriteAllTextAsync(Path.Combine(outputPath, "manifest.json"), JsonSerializer.Serialize(manifest, serializerOptions));

            foreach (var codeObject in allObjects.Values)
            {
                await File.WriteAllTextAsync(Path.Combine(outputPath, "details", $"{codeObject.Id}.json"), JsonSerializer.Serialize(codeObject, serializerOptions));
            }

            Console.WriteLine("Analysis complete.");
            Console.WriteLine($"Manifest and details written to '{outputPath}'");

            return 0;
        }
    }
}