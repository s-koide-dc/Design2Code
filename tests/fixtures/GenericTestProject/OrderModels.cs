using System.Collections.Generic;

namespace OrderSystem.Models
{
    public enum OrderStatus { Pending, Shipped, Delivered }

    public record Product(string Id, string Name, decimal Price);

    public record OrderItem(Product Product, int Quantity);

    public class OrderProcessor
    {
        public OrderStatus Status { get; set; } = OrderStatus.Pending;

        public decimal CalculateTotal(List<OrderItem> items)
        {
            if (items == null || items.Count == 0) return 0m;

            decimal total = 0m;
            foreach (var item in items)
            {
                total += item.Product.Price * item.Quantity;
            }
            return total;
        }
    }
}
