namespace Bank;

public sealed class Account
{
    public Account(string id, decimal balance)
    {
        Id = id;
        Balance = balance;
    }

    public string Id { get; }

    public decimal Balance { get; internal set; }
}
