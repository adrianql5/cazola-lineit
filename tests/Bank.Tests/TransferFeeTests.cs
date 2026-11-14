using Bank;
using Bank.Payments;
using Xunit;

public class TransferFeeTests
{
    [Fact]
    public void Transfer_charges_a_fee_to_the_sender()
    {
        var from = new Account("A", 1000m);
        var to = new Account("B", 0m);
        new TransferService().Transfer(from, to, 100m);
        Assert.Equal(898.5m, from.Balance);
        Assert.Equal(100m, to.Balance);
    }
}
