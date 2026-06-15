-- Seed default policy snapshots (migrated from tariff_calculator.py)
-- Safe to re-run: ON CONFLICT DO NOTHING

INSERT INTO public.policy_snapshots (version, policy_type, effective_date, policy_json)
VALUES (
    '2025-06-02',
    'FTA',
    '2025-06-02',
    '{
        "country_codes": {
            "australia": ["AU"],
            "bahrain": ["BH"],
            "canada": ["CA"],
            "chile": ["CL"],
            "colombia": ["CO"],
            "israel": ["IL"],
            "jordan": ["JO"],
            "south korea": ["KR"],
            "korea": ["KR"],
            "mexico": ["MX", "CA"],
            "morocco": ["MA"],
            "oman": ["OM"],
            "panama": ["PA", "P"],
            "peru": ["PE"],
            "singapore": ["SG", "S"],
            "india": ["A", "A+", "A*"],
            "indonesia": ["A", "A*"],
            "philippines": ["A", "A*"],
            "thailand": ["A", "A*"],
            "bangladesh": ["A", "A+", "A*"],
            "cambodia": ["A", "A*"],
            "pakistan": ["A", "A*"],
            "sri lanka": ["A", "A*"],
            "ethiopia": ["D"],
            "kenya": ["D"],
            "ghana": ["D"],
            "vietnam": []
        }
    }'::jsonb
)
ON CONFLICT (version, policy_type) DO NOTHING;

INSERT INTO public.policy_snapshots (version, policy_type, effective_date, policy_json)
VALUES (
    '2025-06-02',
    'SECTION_301',
    '2025-06-02',
    '{
        "china_origins": ["china", "prc", "people''s republic of china", "hong kong"],
        "chapter_rates": {
            "84": "25%", "85": "25%", "86": "25%", "87": "25%", "88": "25%", "89": "25%", "90": "25%",
            "40": "25%", "68": "25%", "69": "25%", "70": "25%", "73": "25%", "74": "25%", "75": "25%",
            "76": "25%", "82": "25%", "83": "25%", "33": "25%", "36": "25%", "37": "25%", "38": "25%",
            "39": "25%", "42": "25%", "43": "25%", "44": "25%", "45": "25%", "46": "25%", "47": "25%",
            "48": "25%", "49": "25%", "56": "25%", "57": "25%", "58": "25%", "59": "25%", "72": "25%",
            "94": "25%", "61": "7.5%", "62": "7.5%", "63": "7.5%", "64": "7.5%", "65": "7.5%",
            "95": "7.5%", "96": "7.5%"
        }
    }'::jsonb
)
ON CONFLICT (version, policy_type) DO NOTHING;

INSERT INTO public.policy_snapshots (version, policy_type, effective_date, policy_json)
VALUES (
    '2025-06-02',
    'IEEPA',
    '2025-06-02',
    '{
        "rates": {
            "china": {"rate": "20%", "note": "IEEPA additional tariff on China-origin goods effective Feb 4, 2025"},
            "hong kong": {"rate": "20%", "note": "IEEPA additional tariff on Hong Kong-origin goods effective Feb 4, 2025"},
            "mexico": {"rate": "25%", "note": "IEEPA tariff on non-USMCA goods from Mexico effective Mar 4, 2025"},
            "canada": {"rate": "25%", "note": "IEEPA tariff on non-USMCA goods from Canada effective Mar 4, 2025"}
        },
        "usmca_exempt_keys": ["mexico", "canada"]
    }'::jsonb
)
ON CONFLICT (version, policy_type) DO NOTHING;
