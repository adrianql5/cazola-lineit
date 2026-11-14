using Bank;
using Bank.Payments;
using Xunit;

public class TransferServiceTests
{
    [Fact]
    public void Transfer_moves_the_amount()
    {
        var from = new Account("A", 100m);
        var to = new Account("B", 0m);
        new TransferService().Transfer(from, to, 40m);
        Assert.Equal(60m, from.Balance);
        Assert.Equal(40m, to.Balance);
    }

    [Fact]
    public void Transfer_refuses_more_than_the_balance()
    {
        var from = new Account("A", 10m);
        Assert.Throws<InvalidOperationException>(() => new TransferService().Transfer(from, new Account("B", 0m), 20m));
    }
}
