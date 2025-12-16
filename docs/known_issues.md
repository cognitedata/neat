## Ad-blockers causing NeatSession initialization errors

When initializing a `NeatSession`, you may encounter the following error if you have ad-blockers enabled:

```python
ProtocolError: ('Connection aborted.', HTTPException('Failed to fetch'))
MaxRetryError: HTTPSConnectionPool(host='api-eu.mixpanel.com', port=443): Max retries exceeded with url: /engage (Caused by ProtocolError('Connection aborted.', HTTPException('Failed to fetch')))
```

**Cause**: This error occurs because NEAT attempts to send anonymous usage analytics to Mixpanel, but ad-blockers prevent the connection.

**Solution**: You will need to disable ad-blocker or whitelist mixpanel.com in your ad-blocker settings.