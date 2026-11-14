namespace Bank.Payments;

public sealed class TransferService
{
    /// <summary>Moves money between two accounts. The sender never ends up below zero.</summary>
    public void Transfer(Account from, Account to, decimal amount)
    {
        if (amount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(amount), "A transfer must move a positive amount.");
        }

        if (from.Balance < amount)
        {
            throw new InvalidOperationException("Insufficient funds.");
        }

        from.Balance -= amount;
        to.Balance += amount;
    }
}
