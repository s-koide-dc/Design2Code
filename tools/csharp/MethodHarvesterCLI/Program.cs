using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MethodHarvesterCLI
{
    class Program
    {
        private const string IntentAttrName = "IntentAttribute";
        private const string CapabilitiesAttrName = "CapabilitiesAttribute";
        private const string ParamRoleAttrName = "ParamRoleAttribute";

        static void Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.Error.WriteLine("Usage: MethodHarvesterCLI <Assembly1> <Assembly2> ...");
                return;
            }

            var methods = new List<MethodInfoData>();
            var map = LoadCapabilityMap(args, out var filteredArgs);
            var assemblies = filteredArgs.Length > 0 ? filteredArgs : args;
            var options = new JsonSerializerOptions 
            { 
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
            };

            foreach (var arg in assemblies)
            {
                try
                {
                    Assembly? asm = null;
                    if (File.Exists(arg))
                    {
                        asm = Assembly.LoadFrom(arg);
                    }
                    else
                    {
                        try 
                        {
                            asm = Assembly.Load(arg);
                        }
                        catch
                        {
                            asm = AppDomain.CurrentDomain.GetAssemblies().FirstOrDefault(a => a.GetName().Name == arg);
                            if (asm == null)
                            {
                                var systemPath = Path.GetDirectoryName(typeof(object).Assembly.Location);
                                if (systemPath != null)
                                {
                                    var dllPath = Path.Combine(systemPath, arg + ".dll");
                                    if (File.Exists(dllPath))
                                    {
                                        asm = Assembly.LoadFrom(dllPath);
                                    }
                                }
                            }
                        }
                    }

                    if (asm == null)
                    {
                        Console.Error.WriteLine($"Failed to load assembly: {arg}");
                        continue;
                    }

                    Console.Error.WriteLine($"Harvesting from: {asm.FullName}");
                    methods.AddRange(HarvestAssembly(asm));
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"Error processing {arg}: {ex.Message}");
                }
            }

            var result = new { methods = methods };
            Console.WriteLine(JsonSerializer.Serialize(result, options));
        }

        static List<MethodInfoData> HarvestAssembly(Assembly asm)
        {
            var results = new List<MethodInfoData>();
            // 修正: 'Repo' や 'Data' を含む不適切な名前空間を最初から排除する
            var types = asm.GetTypes()
                .Where(t => t.IsPublic && !t.IsObsolete())
                .Where(t => {
                    string fn = t.FullName ?? "";
                    return !fn.Contains("Repo") && !fn.Contains("Data.Repo") && !fn.Contains("Order") && !fn.Contains("Product");
                });

            foreach (var type in types)
            {
                foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly))
                {
                    if (method.IsSpecialName) continue; 
                    if (method.IsObsolete()) continue;

                    try 
                    {
                        var data = new MethodInfoData
                        {
                            Id = $"{type.FullName}.{method.Name}".ToLower(),
                            Name = method.Name,
                            Class = type.FullName ?? "Unknown",
                            ReturnType = GetFriendlyName(method.ReturnType),
                            Params = method.GetParameters().Select(p => new ParamData
                            {
                                Name = p.Name ?? "unnamed",
                                Type = GetFriendlyName(p.ParameterType),
                                Role = ResolveParamRole(p, type, method, map)
                            }).ToList(),
                            IsStatic = method.IsStatic,
                            Intent = ResolveIntent(method, type, map),
                            Capabilities = ResolveCapabilities(method, type, map),
                            Tags = new List<string>(),
                            Code = GenerateCodeTemplate(method, type),
                            Definition = method.ToString() ?? "",
                            // Tier 1: Systemコア, Tier 2: 共通ライブラリ, Tier 3: インフラ・内部実装
                            Tier = (type.FullName?.StartsWith("System.") ?? false) ? 1 : 2
                        };
                        results.Add(data);
                    }
                    catch { }
                }
            }
            return results;
        }

        static CapabilityMap? LoadCapabilityMap(string[] args, out string[] filteredArgs)
        {
            filteredArgs = args;
            string? mapPath = null;
            if (args.Length >= 2 && args[0] == "--map")
            {
                mapPath = args[1];
                filteredArgs = args.Skip(2).ToArray();
            }
            if (string.IsNullOrWhiteSpace(mapPath))
            {
                mapPath = Environment.GetEnvironmentVariable("METHOD_CAPABILITY_MAP");
            }
            if (string.IsNullOrWhiteSpace(mapPath))
            {
                var baseDir = AppContext.BaseDirectory;
                var candidate = Path.Combine(baseDir, "method_capability_map.json");
                if (File.Exists(candidate))
                    mapPath = candidate;
            }
            if (string.IsNullOrWhiteSpace(mapPath) || !File.Exists(mapPath))
                return null;
            try
            {
                var json = File.ReadAllText(mapPath);
                var map = JsonSerializer.Deserialize<CapabilityMap>(json);
                if (map == null || map.Methods == null)
                    return null;
                var normalized = new Dictionary<string, CapabilityEntry>();
                foreach (var kv in map.Methods)
                {
                    var key = kv.Key?.Trim();
                    if (string.IsNullOrWhiteSpace(key)) continue;
                    normalized[key] = kv.Value;
                    normalized[key.ToLowerInvariant()] = kv.Value;
                }
                map.Methods = normalized;
                return map;
            }
            catch
            {
                return null;
            }
        }

        static string GetQualifiedMethodName(Type type, MethodInfo method)
        {
            var typeName = type.FullName ?? "Unknown";
            return $"{typeName}.{method.Name}";
        }

        static string GetFriendlyName(Type type)
        {
            if (type == typeof(int)) return "int";
            if (type == typeof(string)) return "string";
            if (type == typeof(bool)) return "bool";
            if (type == typeof(void)) return "void";
            
            if (type.IsGenericType)
            {
                var name = type.Name.Split('`')[0];
                var args = string.Join(", ", type.GetGenericArguments().Select(GetFriendlyName));
                return $"{name}<{args}>";
            }
            return type.Name;
        }

        static string? GetParamRoleFromAttributes(ParameterInfo param)
        {
            return GetSingleStringAttribute(param.CustomAttributes, ParamRoleAttrName);
        }

        static string? GetIntentFromAttributes(MethodInfo method)
        {
            return GetSingleStringAttribute(method.CustomAttributes, IntentAttrName);
        }

        static List<string> GetCapabilitiesFromAttributes(MethodInfo method)
        {
            return GetStringListAttribute(method.CustomAttributes, CapabilitiesAttrName);
        }

        static string? ResolveIntent(MethodInfo method, Type type, CapabilityMap? map)
        {
            var intent = GetIntentFromAttributes(method);
            if (!string.IsNullOrWhiteSpace(intent)) return intent;
            if (map == null) return null;
            var key = GetQualifiedMethodName(type, method);
            if (map.Methods.TryGetValue(key, out var entry) && !string.IsNullOrWhiteSpace(entry.Intent))
                return entry.Intent;
            return null;
        }

        static List<string> ResolveCapabilities(MethodInfo method, Type type, CapabilityMap? map)
        {
            var caps = GetCapabilitiesFromAttributes(method);
            if (caps.Count > 0) return caps;
            if (map == null) return new List<string>();
            var key = GetQualifiedMethodName(type, method);
            if (map.Methods.TryGetValue(key, out var entry) && entry.Capabilities != null)
                return entry.Capabilities.Distinct().ToList();
            return new List<string>();
        }

        static string? ResolveParamRole(ParameterInfo param, Type type, MethodInfo method, CapabilityMap? map)
        {
            var role = GetParamRoleFromAttributes(param);
            if (!string.IsNullOrWhiteSpace(role)) return role;
            if (map == null) return null;
            var key = GetQualifiedMethodName(type, method);
            if (map.Methods.TryGetValue(key, out var entry) && entry.ParamRoles != null)
            {
                var pName = param.Name ?? "";
                if (entry.ParamRoles.TryGetValue(pName, out var mapped) && !string.IsNullOrWhiteSpace(mapped))
                    return mapped;
            }
            return null;
        }

        static string? GetSingleStringAttribute(IEnumerable<CustomAttributeData> attrs, string attrName)
        {
            foreach (var attr in attrs)
            {
                if (!IsAttrName(attr, attrName)) continue;
                var fromCtor = ExtractFirstString(attr);
                if (!string.IsNullOrWhiteSpace(fromCtor)) return fromCtor;
                var fromNamed = ExtractNamedString(attr);
                if (!string.IsNullOrWhiteSpace(fromNamed)) return fromNamed;
            }
            return null;
        }

        static List<string> GetStringListAttribute(IEnumerable<CustomAttributeData> attrs, string attrName)
        {
            var results = new List<string>();
            foreach (var attr in attrs)
            {
                if (!IsAttrName(attr, attrName)) continue;
                var list = ExtractStringList(attr);
                if (list.Count > 0) results.AddRange(list);
            }
            return results.Distinct().ToList();
        }

        static bool IsAttrName(CustomAttributeData attr, string attrName)
        {
            var name = attr.AttributeType.Name;
            if (string.Equals(name, attrName, StringComparison.Ordinal)) return true;
            if (name.EndsWith("Attribute", StringComparison.Ordinal))
            {
                var shortName = name.Substring(0, name.Length - "Attribute".Length);
                var shortTarget = attrName.EndsWith("Attribute", StringComparison.Ordinal)
                    ? attrName.Substring(0, attrName.Length - "Attribute".Length)
                    : attrName;
                return string.Equals(shortName, shortTarget, StringComparison.Ordinal);
            }
            return false;
        }

        static string? ExtractFirstString(CustomAttributeData attr)
        {
            if (attr.ConstructorArguments.Count == 0) return null;
            var arg = attr.ConstructorArguments[0];
            if (arg.Value is string s) return s;
            return null;
        }

        static string? ExtractNamedString(CustomAttributeData attr)
        {
            foreach (var named in attr.NamedArguments)
            {
                if (named.TypedValue.Value is string s) return s;
            }
            return null;
        }

        static List<string> ExtractStringList(CustomAttributeData attr)
        {
            var results = new List<string>();
            if (attr.ConstructorArguments.Count == 1)
            {
                var arg = attr.ConstructorArguments[0];
                if (arg.Value is string s)
                {
                    results.Add(s);
                }
                else if (arg.Value is IReadOnlyCollection<CustomAttributeTypedArgument> arr)
                {
                    foreach (var item in arr)
                    {
                        if (item.Value is string sv) results.Add(sv);
                    }
                }
            }
            foreach (var named in attr.NamedArguments)
            {
                if (named.TypedValue.Value is IReadOnlyCollection<CustomAttributeTypedArgument> arr)
                {
                    foreach (var item in arr)
                    {
                        if (item.Value is string sv) results.Add(sv);
                    }
                }
            }
            return results;
        }

        static string GenerateCodeTemplate(MethodInfo m, Type t)
        {
            var args = string.Join(", ", m.GetParameters().Select(p => $"{{{p.Name}}}"));
            if (m.IsStatic)
            {
                if (m.Name.Contains("Async"))
                    return $"await {t.FullName}.{m.Name}({args})";
                return $"{t.FullName}.{m.Name}({args})";
            }
            else
            {
                return $"{{target}}.{m.Name}({args})";
            }
        }
    }

    static class Extensions
    {
        public static bool IsObsolete(this MemberInfo member)
        {
            return member.GetCustomAttributes(typeof(ObsoleteAttribute), false).Any();
        }
    }

    class MethodInfoData
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Class { get; set; } = "";
        public string ReturnType { get; set; } = "";
        public List<ParamData> Params { get; set; } = new List<ParamData>();
        public bool IsStatic { get; set; }
        public List<string> Tags { get; set; } = new List<string>();
        public List<string> Capabilities { get; set; } = new List<string>();
        public string? Intent { get; set; }
        public string Code { get; set; } = "";
        public string Definition { get; set; } = "";
        public int Tier { get; set; }
    }

    class ParamData
    {
        public string Name { get; set; } = "";
        public string Type { get; set; } = "";
        public string? Role { get; set; }
    }

    class CapabilityMap
    {
        public int Version { get; set; }
        public Dictionary<string, CapabilityEntry> Methods { get; set; } = new Dictionary<string, CapabilityEntry>();
    }

    class CapabilityEntry
    {
        public string? Intent { get; set; }
        public List<string>? Capabilities { get; set; }
        public Dictionary<string, string>? ParamRoles { get; set; }
    }
}
