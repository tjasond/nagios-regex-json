
## Nagios JSON RegEx plugin

This plugin consumes a JSON document via HTTP(S), flattens its structure, and applies specified regular expressions in order to provide nagios-appropriate warnings/errors.  This plugin is a derivative of [Nagios Json Plugin](https://github.com/drewkerrigan/nagios-http-json).  Complete program args are [available here](#program_args)

### Concept

Given a JSON document containing metric/status information:

```
  "meta": {
    "build": "12345",
    "version": "1",
  },
  "non_critical": [
  {
    "MetricOne": "15"
  }],
  "critical": [
  {
    "id": "MetricTwo",
    "status": "OK"
  },
  {
    "id": "MetricThree",
    "status": "ALARM"
  }]
```

Construct expressions that will expose warnings and errors:

1. Example: All critical items must report "OK", or else report a critical error:
  ```
  ./check_json.py -H localhost -p /status -Q "critical\..*\.status,OK,1"
  ```
  Output:
  ```
  CRITICAL: Status CRITICAL. ; Critical: critical.[1].status=ALARM; critical.[1].id=MetricThree;
  ```

  Explanation: The 'Q' argument consists of 3 parts, delimited by a comma: [regular_expression],[expected_value],[context_level]

  * Regular Expression: An expression to apply against properties in the [flattened](#flattened_json) JSON document

  * Expected Value: Comma-separated list of expected values (case-sensitive)

  * Context Level: The number of levels to "walk up" in order to provide adequate context in an error message.  In this example, setting the context to 1 outputs all sibling properties, which allows the id, "MetricThree", to be included in the output.

2. Example: A key named "MetricTwo" must exist in the non_critical section, or else report a warning:
  ```
    ./check_json.py -H localhost -p /status -e "non_critical\..*\.MetricTwo"
  ```
  Output:
  ```
  WARNING: Status WARNING. ; Warnings:  non_critical\..*\.MetricTwo Not Found;
  ```

  Explanation: The 'e' argument consists a regular expression that is applied to each of the [flattened](#flattened_json) JSON document properties.  

3.  Example: A key named "MetricOne" in the non_critical section must have a value that is not between 10 and 20, or else report a warning:
  ```
  ./check_json.py -H localhost -p /status -w "non_critical\..*\.MetricOne,@10:20,0"
  ```
  Output:
  ```
  WARNING: Status WARNING. ; Warnings:  non_critical.[0].MetricOne=15;
  ```
  Explanation: The "w" argument consists of 3 parts, delimited by a comma:
  [regular_expression],[range_expression],[context_level]

  * Regular Expression: An expression to apply against properties in the [flattened](#flattened_json) JSON document

  * Range Expression: Nagios [range expression](https://nagios-plugins.org/doc/guidelines.html#THRESHOLDFORMAT)

  * Context Level: The number of levels to "walk up" in order to provide adequate context in an error message.  In this example, all necessary context is provided by the key itself, so 0 is specified.


### Reference:

#### <a name="flattened_json">Flattened JSON Document</a> properties from the example above:
```
meta.build=12345
meta.version=1
non_critical.[0].MetricOne=15
critical.[0].id=MetricTwo
critical.[0].status=OK
critical.[1].id=MetricThree
critical.[1].status=ALARM
```
#### <a name="program_args">Complete list</a> of program arguments:
```
optional arguments:
  -h, --help            show this help message and exit
  -q [KEY_VALUE_LIST [KEY_VALUE_LIST ...]], --key_equals [KEY_VALUE_LIST [KEY_VALUE_LIST ...]]
                        Checks equality of these key regular expressions and
                        values (key_regex,value,level key2_regex,value2,level)
                        to determine status. Multiple key values can be
                        delimited with colon (key_regex,value1:value2,level).
                        Return warning if equality check fails
  -Q [KEY_VALUE_LIST_CRITICAL [KEY_VALUE_LIST_CRITICAL ...]], --key_equals_critical [KEY_VALUE_LIST_CRITICAL [KEY_VALUE_LIST_CRITICAL ...]]
                        Same as -q but return critical if equality check
                        fails.
  -e [KEY_LIST [KEY_LIST ...]], --key_exists [KEY_LIST [KEY_LIST ...]]
                        Checks existence of these key regular expressions to
                        determine status (key_regex). Return warning if key is
                        not present.
  -E [KEY_LIST_CRITICAL [KEY_LIST_CRITICAL ...]], --key_exists_critical [KEY_LIST_CRITICAL [KEY_LIST_CRITICAL ...]]
                        Same as -e but return critical if key is not present.
  -w [KEY_THRESHOLD_WARNING [KEY_THRESHOLD_WARNING ...]], --warning [KEY_THRESHOLD_WARNING [KEY_THRESHOLD_WARNING ...]]
                        Warning threshold for these values
                        (key1_regex,WarnRange,level
                        key2_regex,WarnRange,level). WarnRange is in the
                        format [@]start:end, more information at nagios-
                        plugins.org/doc/guidelines.html.
  -c [KEY_THRESHOLD_CRITICAL [KEY_THRESHOLD_CRITICAL ...]], --critical [KEY_THRESHOLD_CRITICAL [KEY_THRESHOLD_CRITICAL ...]]
                        Critical threshold for these values
                        (key1_regex,CriticalRange,level
                        key2,CriticalRange,level. CriticalRange is in the
                        format [@]start:end, more information at nagios-
                        plugins.org/doc/guidelines.html.
  -v, --verbose         Verbose Output
  -d, --debug           Debug mode.
  -s, --ssl             HTTPS mode.
  -H HOST, --host HOST  Host.
  -P PORT, --port PORT  TCP port
  -p PATH, --path PATH  Path.
  -t TIMEOUT, --timeout TIMEOUT
                        Connection timeout (seconds)
  -B AUTH, --basic-auth AUTH
                        Basic auth string "username:password"
```
