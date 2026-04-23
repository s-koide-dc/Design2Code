namespace BankingApp.Logic
{
    public interface ICurrencyConverter
    {
        decimal Convert(decimal amount, string targetCurrency);
    }

    public class AccountService
    {
        private readonly ICurrencyConverter _converter;
        public decimal Balance { get; private set; }

        public AccountService(ICurrencyConverter converter)
        {
            _converter = converter;
            Balance = 1000m;
        }

        public decimal Withdraw(decimal amount, string currency)
        {
            if (amount <= 0) throw new System.ArgumentException("Amount must be positive");
            
            decimal localAmount = (currency == "USD") ? _converter.Convert(amount, "JPY") : amount;
            
            if (Balance >= localAmount)
            {
                Balance -= localAmount;
                return Balance;
            }
            return -1m;
        }
    }
}
