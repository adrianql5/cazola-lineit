using Bank.Infrastructure;
using Xunit;

public class RetryTests
{
    [Fact]
    public void Run_tries_again_after_a_timeout()
    {
        var calls = 0;
        var result = Retry.Run(() => ++calls < 3 ? throw new TimeoutException() : "ok");
        Assert.Equal("ok", result);
        Assert.Equal(3, calls);
    }

    [Fact]
    public void Run_gives_up_after_the_last_attempt()
    {
        Assert.Throws<TimeoutException>(() => Retry.Run<string>(() => throw new TimeoutException(), attempts: 2));
    }
}
