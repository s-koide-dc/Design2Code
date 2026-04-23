namespace DependencyDemo
{
    public class ServiceB
    {
        public string GetData()
        {
            return "Data from B";
        }
    }

    public class ServiceA
    {
        private readonly ServiceB _serviceB;

        public ServiceA(ServiceB serviceB)
        {
            _serviceB = serviceB;
        }

        public string Process()
        {
            var data = _serviceB.GetData();
            return $"Processed: {data}";
        }
    }

    public class Client
    {
        public void Run()
        {
            var b = new ServiceB();
            var a = new ServiceA(b);
            System.Console.WriteLine(a.Process());
        }
    }
}
