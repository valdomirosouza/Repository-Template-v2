# GovernanceApi

All URIs are relative to *http://localhost:8000*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**getSloStatus**](GovernanceApi.md#getslostatus) | **GET** /v1/governance/slo-status | SLO targets and honest observed status |



## getSloStatus

> SLOStatusResponse getSloStatus()

SLO targets and honest observed status

Returns every SLO defined in docs/sre/slo/slo.yaml with an honest observed block. Requires a bearer JWT (read access). target/target_ms/target_max and window are the real configured SLO definitions. observed.data_available is true only where a real in-process sample exists (api-gateway availability/error-rate, scoped as a process-lifetime sample); everywhere else it is false with a note — no observed number is ever fabricated (computing 30-day SLO compliance / burn-rate needs a metrics-query layer the service lacks). SPEC-API-004, CLAUDE.md §3.6.

### Example

```ts
import {
  Configuration,
  GovernanceApi,
} from '';
import type { GetSloStatusRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const config = new Configuration({ 
    // Configure HTTP bearer authorization: bearerAuth
    accessToken: "YOUR BEARER TOKEN",
  });
  const api = new GovernanceApi(config);

  try {
    const data = await api.getSloStatus();
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**SLOStatusResponse**](SLOStatusResponse.md)

### Authorization

[bearerAuth](../README.md#bearerAuth)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | SLO targets and honest observed status |  -  |
| **401** | Missing or invalid bearer token |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)

