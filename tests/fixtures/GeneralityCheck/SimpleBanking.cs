namespace SimpleBanking
{
    public class Account
    {
        public string AccountNumber { get; set; }
        public decimal Balance { get; private set; }

        public Account(string accountNumber, decimal initialBalance)
        {
            AccountNumber = accountNumber;
            Balance = initialBalance;
        }

        public void Deposit(decimal amount)
        {
            if (amount <= 0) throw new System.ArgumentException("Amount must be positive");
            Balance += amount;
        }

        public bool Withdraw(decimal amount)
        {
            if (amount <= 0) throw new System.ArgumentException("Amount must be positive");
            if (Balance >= amount)
            {
                Balance -= amount;
                return true;
            }
            return false;
        }
    }
}
