namespace Bank.Infrastructure;

/// <summary>How the bank calls services outside it.</summary>
public static class Retry
{
    /// <summary>Runs the operation once; a failure goes back to the caller.</summary>
    public static T Run<T>(Func<T> operation) => operation();
}
