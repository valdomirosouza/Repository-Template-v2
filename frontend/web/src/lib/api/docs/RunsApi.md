# RunsApi

All URIs are relative to *http://localhost:8000*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**getRunTrace**](RunsApi.md#getruntrace) | **GET** /v1/runs/{request_id} | Get a request\&#39;s execution trace |



## getRunTrace

> RunTraceResponse getRunTrace(requestId)

Get a request\&#39;s execution trace

Returns the execution trace for a single submitted request: its state plus a timeline of audit events that can be REALLY associated with it. Requires a bearer JWT (read access). timeline_association names the strategy that built the timeline — the audit store is not indexed by the domain request_id, so an exact trace is only available when an event\&#39;s metadata.request_id matches; otherwise timeline is empty and timeline_association is \&quot;none\&quot; (SPEC-API-004 §9.1, CLAUDE.md §3.6 — no fabricated linkage).

### Example

```ts
import {
  Configuration,
  RunsApi,
} from '';
import type { GetRunTraceRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const config = new Configuration({ 
    // Configure HTTP bearer authorization: bearerAuth
    accessToken: "YOUR BEARER TOKEN",
  });
  const api = new RunsApi(config);

  const body = {
    // string
    requestId: 38400000-8cf0-11bd-b23e-10b96e4ef00d,
  } satisfies GetRunTraceRequest;

  try {
    const data = await api.getRunTrace(body);
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```

### Parameters


| Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **requestId** | `string` |  | [Defaults to `undefined`] |

### Return type

[**RunTraceResponse**](RunTraceResponse.md)

### Authorization

[bearerAuth](../README.md#bearerAuth)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | Request execution trace |  -  |
| **401** | Missing or invalid bearer token |  -  |
| **404** | Run not found (unknown request_id or expired) |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)

