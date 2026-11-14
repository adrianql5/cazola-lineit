namespace Bank.Infrastructure;

/// <summary>How the bank calls services outside it.</summary>
public static class Retry
{
    /// <summary>Runs the operation, trying again after a timeout, up to <paramref name="attempts"/> times.</summary>
    public static T Run<T>(Func<T> operation, int attempts = 3)
    {
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                return operation();
            }
            catch (TimeoutException) when (attempt < attempts)
            {
                Thread.Sleep(100 * attempt);
            }
        }
    }
}
