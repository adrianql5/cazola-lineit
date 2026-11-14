namespace Bank.Payments;

public sealed class TransferService
{
    public const double FeeRate = 0.015;

    /// <summary>Moves money between two accounts and charges the sender a 1.5% fee.</summary>
    public void Transfer(Account from, Account to, decimal amount)
    {
        if (from.Balance < amount)
        {
            throw new InvalidOperationException("Insufficient funds.");
        }

        var fee = (decimal)((double)amount * FeeRate);
        from.Balance -= amount + fee;
        to.Balance += amount;
    }
}
