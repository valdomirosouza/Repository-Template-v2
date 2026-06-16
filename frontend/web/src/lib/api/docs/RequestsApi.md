# RequestsApi

All URIs are relative to *http://localhost:8000*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**getRequestStatus**](RequestsApi.md#getrequeststatus) | **GET** /v1/requests/{request_id} | Poll request processing status |
| [**submitRequest**](RequestsApi.md#submitrequest) | **POST** /v1/requests | Submit a domain request for async processing |



## getRequestStatus

> RequestOut getRequestStatus(requestId)

Poll request processing status

### Example

```ts
import {
  Configuration,
  RequestsApi,
} from '';
import type { GetRequestStatusRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const api = new RequestsApi();

  const body = {
    // string
    requestId: 38400000-8cf0-11bd-b23e-10b96e4ef00d,
  } satisfies GetRequestStatusRequest;

  try {
    const data = await api.getRequestStatus(body);
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

[**RequestOut**](RequestOut.md)

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | Current request status |  -  |
| **404** | Request not found |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)


## submitRequest

> RequestOut submitRequest(requestIn, idempotencyKey)

Submit a domain request for async processing

Accepts a request and publishes it to the async pipeline. Returns 202 immediately. Poll GET /v1/requests/{request_id} for the result. PII in the request body is masked before the event is published. Send an optional &#x60;Idempotency-Key&#x60; header to make retries safe (SPEC-API-002): a repeat with the same body replays the original 202; a repeat with a different body returns 422 &#x60;IDEMPOTENCY_KEY_REUSED&#x60;. 

### Example

```ts
import {
  Configuration,
  RequestsApi,
} from '';
import type { SubmitRequestRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const api = new RequestsApi();

  const body = {
    // RequestIn
    requestIn: ...,
    // string | Opaque client key (printable ASCII, 8–200 chars) to de-duplicate retried submissions. (optional)
    idempotencyKey: idempotencyKey_example,
  } satisfies SubmitRequestRequest;

  try {
    const data = await api.submitRequest(body);
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
| **requestIn** | [RequestIn](RequestIn.md) |  | |
| **idempotencyKey** | `string` | Opaque client key (printable ASCII, 8–200 chars) to de-duplicate retried submissions. | [Optional] [Defaults to `undefined`] |

### Return type

[**RequestOut**](RequestOut.md)

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: `application/json`
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **202** | Request accepted for async processing |  -  |
| **422** | Validation error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)

