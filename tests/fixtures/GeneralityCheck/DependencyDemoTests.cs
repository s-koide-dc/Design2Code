using Xunit;
using DependencyDemo;

namespace DependencyDemo.Tests
{
    public class ServiceATests
    {
        [Fact]
        public void Process_ShouldReturnExpectedString()
        {
            var b = new ServiceB();
            var a = new ServiceA(b);
            var result = a.Process();
            Assert.Contains("Data from B", result);
        }
    }
}
