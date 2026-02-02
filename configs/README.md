# Funnel Friction Auditor - Configuration Files

This directory contains JSON configuration files for different product flows.

## File Structure

Each configuration file defines:
- Product information (name, type)
- Flow steps with actions
- Click handlers and selectors
- Special handling rules (redirects, continue on failure, etc.)

## Adding New Products

1. Create a new JSON file: `configs/{product_type}_{product_name}.json`
2. Define the flow steps following the structure below
3. Add any custom click handlers to the main validator class if needed

## Configuration Schema

```json
{
  "product_name": "Product Name",
  "product_type": "mobile|broadband|tv",
  "flow_name": "Display Name",
  "start_url": "https://...",
  "steps": [
    {
      "name": "Step Name",
      "step_number": 1,
      "expected_url": "url pattern",
      "actions": [
        {
          "type": "wait_for_selector|click",
          "selector": "CSS selector or special handler name",
          "timeout": 20000
        }
      ],
      "optional": false,
      "continue_on_failure": false,
      "redirect_handling": {
        "detect_patterns": ["/pattern1", "/pattern2"],
        "redirect_back_to": "previous_step_url|specific_url"
      }
    }
  ],
  "click_handlers": {
    "HANDLER_NAME": {
      "handler": "method_name",
      "selectors": ["selector1", "selector2"]
    }
  }
}
```

## Examples

- `sky_mobile_samsung_s25_ultra.json` - Samsung Galaxy S25 Ultra mobile flow
- `sky_broadband_*.json` - Broadband product flows (to be added)
- `sky_tv_*.json` - TV product flows (to be added)

