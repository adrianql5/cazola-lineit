using Bank.Infrastructure;

namespace Bank.Payments;

public interface ICardNetwork
{
    /// <summary>Charges the card. Each call is a new charge: the network does not deduplicate.</summary>
    string Charge(string card, decimal amount);
}

public sealed class CardGateway(ICardNetwork network)
{
    public string Charge(string card, decimal amount)
        => Retry.Run(() => network.Charge(card, amount));
}
