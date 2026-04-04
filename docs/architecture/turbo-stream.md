# Turbo-Stream Format Discovery & Implementation

## Summary

Successfully identified that Rouvy uses the **turbo-stream** format from the Remix framework for API responses. Implemented a generic Python decoder that works across all tested endpoints.

## Format Discovery

### Initial Observations

- Responses contained compressed JSON with indexed references like `{"_1":2,"_70":71}`
- Special array formats like `["D", timestamp]` for dates
- Multi-line responses with promise resolutions
- Values appeared to use numeric indices instead of direct values

### Investigation Process

1. **Web search** for similar formats revealed Remix's turbo-stream
2. **Confirmed** from https://github.com/jacob-ebey/turbo-stream
3. **Analyzed** actual response structure to understand resolution rules
4. **Tested** multiple endpoints to verify format consistency

## Format Specification

### Core Concepts

**Turbo-stream** is a streaming data transport format that:

- Supports more types than JSON (Promises, Dates, Maps, Sets, etc.)
- Uses indexed references to deduplicate repeated values
- Enables streaming of async data via Promises
- Popular in Remix/React Router server-rendered applications

### Format Rules

1. **Main Structure**: Top-level array with interleaved keys and values

2. **Indexed References**:

   ```json
   [
     {"_73": -5, "_76": 77, "_78": 79},
     "firstName",      // index 73
     "lastName",       // index 74
     "email",          // index 76
     "user@email.com", // index 77
     "userProfile",    // index 78
     {...}             // index 79
   ]
   ```

   - `_N` keys reference index N for the actual key name
   - Values of `_N` properties are ALSO index references
   - Other integer values are literals

3. **Special Types**:
   - **Dates**: `["D", milliseconds_since_epoch]`
   - **Promises**: `["P", promise_id]` - resolved in subsequent lines
   - **Undefined**: `-5` integer sentinel
   - **Null**: `-7` integer sentinel

4. **Multi-line Responses**:

   ```text
   Line 1: [{main json array}, ...rest of data]
   Line 2: P132:{"resolved":"data"}
   Line 3: P134:[1,2,3]
   ```

5. **Resolution Strategy**:
   - Integers in indexed object values (`{"_N": value}`) → resolve as index
   - Integers elsewhere → treat as literals
   - Prevents incorrect resolution of numeric data like FTP watts

## Implementation

### Module Structure

```text
custom_components/rouvy/api_client/
  __init__.py         # Exports parser functions
  parser.py           # TurboStreamDecoder + utilities
  client.py           # HTTP client with auth
  config.py           # Configuration
  errors.py           # Custom exceptions
```

### Key Classes

**`TurboStreamDecoder`**

- Main decoder class with index map and promise resolution
- `decode(response_text)` - Entry point for decoding
- `_decode_value(value, resolve_int_as_index)` - Recursive decoder
- `_parse_promise_line(line)` - Parse "PID:value" promise resolutions

**`extract_user_profile(response_text)`**

- Specialized extractor for user-settings.data
- Navigates decoded structure to find userProfile object
- Returns clean dict with normalized field names

**`parse_response(response_text)`**

- Generic decoder for any turbo-stream response
- Returns decoded data structure (typically list or dict)

### Usage Examples

```python
from custom_components.rouvy.api_client

 import RouvyClient, parse_response, extract_user_profile

client = RouvyClient(config)

# Specialized extraction
response = client.get("user-settings.data")
profile = extract_user_profile(response.text)
print(profile['ftp_watts'])  # 165

# Generic parsing
response = client.get("user-settings/zones.data")
decoded = parse_response(response.text)
# Navigate decoded structure manually
```

## Tested Endpoints

All use the same turbo-stream format:

| Endpoint                               | Response Size | Contains                            |
| -------------------------------------- | ------------- | ----------------------------------- |
| `user-settings.data`                   | ~11 KB        | User profile, preferences, nav data |
| `user-settings/zones.data`             | ~12 KB        | Power/HR zones, settings            |
| `user-settings/connected-apps.data`    | ~15 KB        | Connected third-party apps          |
| `profile/overview.data`                | ~73 KB        | Activities, stats, large dataset    |
| `resources/activities-pagination.data` | ~34 KB        | Paginated activity list             |

## Alternative Approaches Considered

1. **Using npm turbo-stream package**
   - Would require Node.js subprocess or JavaScript runtime
   - Adds deployment complexity
   - Rejected in favor of native Python

2. **Port JavaScript implementation**
   - Turbo-stream supports streaming ReadableStreams
   - Full implementation would be complex (promises, streams)
   - Our use case doesn't need streaming - we get full responses
   - Implemented subset sufficient for Rouvy API

3. **Simple JSON parsing**
   - Doesn't handle indexed references
   - Can't decode dates, promises, sentinels
   - Would require manual field extraction per endpoint
   - Rejected - not robust enough

## Future Enhancements

1. **Full turbo-stream support**
   - Implement all type conversions (Map, Set, RegExp, etc.)
   - Add streaming support for large responses
   - Handle more promise resolution patterns

2. **Schema generation**
   - Auto-generate type hints from decoded structures
   - Create dataclasses for known response shapes

3. **Endpoint discovery**
   - Build catalog of all available endpoints
   - Document expected response structure for each

4. **Caching**
   - Cache decoded results keyed by response hash
   - Avoid re-decoding identical responses

## References

- **Turbo-Stream GitHub**: https://github.com/jacob-ebey/turbo-stream
- **Remix Single Fetch Docs**: https://v2.remix.run/docs/guides/single-fetch
- **Format Specification**: Inferred from library code and response analysis
- **Rouvy Implementation**: Uses standard turbo-stream with no custom extensions detected

## Files

- `custom_components/rouvy/api_client/parser.py` - Full parser implementation
- `demo_parser.py` - Comprehensive usage examples
- `test_endpoints.py` - Endpoint discovery/testing script
- `debug_parser.py` - Debug tool for analyzing responses
- `README.md` - Updated with parser documentation
