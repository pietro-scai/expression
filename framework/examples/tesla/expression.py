{
  "models": [
    {
      "inputs": {
        "wacc": {
          "doc": "Weighted average cost of capital",
          "type": "float",
          "value": 0.1,
          "default": 0.1
        },
        "auto_asp": {
          "doc": "Average selling price per vehicle ($)",
          "type": "int",
          "value": 42000,
          "default": 42000
        },
        "net_cash": {
          "doc": "Net cash (cash minus debt) on balance sheet ($M)",
          "type": "int",
          "value": 15000,
          "default": 15000
        },
        "tax_rate": {
          "doc": "Effective corporate tax rate",
          "type": "float",
          "value": 0.15,
          "default": 0.15
        },
        "da_pct_rev": {
          "doc": "D&A as % of revenue (add-back to FCF)",
          "type": "float",
          "value": 0.06,
          "default": 0.06
        },
        "ebit_margin": {
          "doc": "EBIT margin as % of total revenue",
          "type": "float",
          "value": 0.1,
          "default": 0.1
        },
        "nwc_pct_rev": {
          "doc": "Change in NWC as % of incremental revenue",
          "type": "float",
          "value": 0.01,
          "default": 0.01
        },
        "capex_pct_rev": {
          "doc": "CapEx as % of revenue",
          "type": "float",
          "value": 0.08,
          "default": 0.08
        },
        "energy_growth": {
          "doc": "Energy segment annual revenue growth rate",
          "type": "float",
          "value": 0.35,
          "default": 0.35
        },
        "auto_asp_drift": {
          "doc": "Annual ASP change rate (neg = pricing pressure)",
          "type": "float",
          "value": -0.01,
          "default": -0.01
        },
        "energy_rev_base": {
          "doc": "Energy segment revenue, base year ($M)",
          "type": "int",
          "value": 10000,
          "default": 10000
        },
        "services_growth": {
          "doc": "Services segment annual revenue growth rate",
          "type": "float",
          "value": 0.2,
          "default": 0.2
        },
        "terminal_growth": {
          "doc": "Terminal growth rate (long-run perpetuity)",
          "type": "float",
          "value": 0.03,
          "default": 0.03
        },
        "services_rev_base": {
          "doc": "Services & other revenue, base year ($M)",
          "type": "int",
          "value": 8000,
          "default": 8000
        },
        "shares_outstanding": {
          "doc": "Diluted shares outstanding (M)",
          "type": "int",
          "value": 3200,
          "default": 3200
        },
        "auto_deliveries_base": {
          "doc": "Base year vehicle deliveries (units, 2025E)",
          "type": "int",
          "value": 1900000,
          "default": 1900000
        },
        "auto_delivery_growth": {
          "doc": "Annual delivery volume growth rate",
          "type": "float",
          "value": 0.2,
          "default": 0.2
        }
      },
      "tables": [
        {
          "doc": null,
          "kind": "row",
          "name": "deliveries",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 1900000,
            "2026": 2280000,
            "2027": 2736000,
            "2028": 3283200,
            "2029": 3939840,
            "2030": 4727808,
            "2031": 5673369.6,
            "2032": 6808043.52,
            "2033": 8169652.223999999,
            "2034": 9803582.668799998
          },
          "depends_on": [
            "auto_deliveries_base",
            "auto_delivery_growth"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "asp",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 42000,
            "2026": 41580,
            "2027": 41164.2,
            "2028": 40752.558,
            "2029": 40345.032419999996,
            "2030": 39941.5820958,
            "2031": 39542.166274842,
            "2032": 39146.74461209358,
            "2033": 38755.27716597264,
            "2034": 38367.724394312914
          },
          "depends_on": [
            "auto_asp",
            "auto_asp_drift"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "auto_revenue",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 79800,
            "2026": 94802.4,
            "2027": 112625.25119999998,
            "2028": 133798.7984256,
            "2029": 158952.9725296128,
            "2030": 188836.13136518,
            "2031": 224337.32406183385,
            "2032": 266512.7409854586,
            "2033": 316617.1362907248,
            "2034": 376141.157913381
          },
          "depends_on": [
            "asp",
            "deliveries"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "energy_revenue",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 10000,
            "2026": 13500,
            "2027": 18225,
            "2028": 24603.75,
            "2029": 33215.0625,
            "2030": 44840.334375000006,
            "2031": 60534.45140625001,
            "2032": 81721.50939843751,
            "2033": 110324.03768789065,
            "2034": 148937.4508786524
          },
          "depends_on": [
            "energy_growth",
            "energy_rev_base"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "services_revenue",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 8000,
            "2026": 9600,
            "2027": 11520,
            "2028": 13824,
            "2029": 16588.8,
            "2030": 19906.559999999998,
            "2031": 23887.871999999996,
            "2032": 28665.446399999993,
            "2033": 34398.53567999999,
            "2034": 41278.24281599999
          },
          "depends_on": [
            "services_growth",
            "services_rev_base"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "total_revenue",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 97800,
            "2026": 117902.4,
            "2027": 142370.2512,
            "2028": 172226.5484256,
            "2029": 208756.8350296128,
            "2030": 253583.02574018,
            "2031": 308759.64746808383,
            "2032": 376899.6967838961,
            "2033": 461339.7096586154,
            "2034": 566356.8516080334
          },
          "depends_on": [
            "auto_revenue",
            "energy_revenue",
            "services_revenue"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "ebit",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 9780,
            "2026": 11790.24,
            "2027": 14237.02512,
            "2028": 17222.65484256,
            "2029": 20875.68350296128,
            "2030": 25358.302574018002,
            "2031": 30875.964746808386,
            "2032": 37689.969678389614,
            "2033": 46133.97096586155,
            "2034": 56635.68516080335
          },
          "depends_on": [
            "ebit_margin",
            "total_revenue"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "nopat",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 8313,
            "2026": 10021.704,
            "2027": 12101.471352,
            "2028": 14639.256616176,
            "2029": 17744.33097751709,
            "2030": 21554.5571879153,
            "2031": 26244.570034787128,
            "2032": 32036.47422663117,
            "2033": 39213.87532098231,
            "2034": 48140.33238668284
          },
          "depends_on": [
            "ebit",
            "tax_rate"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "da",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 5868,
            "2026": 7074.143999999999,
            "2027": 8542.215071999999,
            "2028": 10333.592905536,
            "2029": 12525.410101776766,
            "2030": 15214.981544410799,
            "2031": 18525.578848085028,
            "2032": 22613.981807033768,
            "2033": 27680.382579516925,
            "2034": 33981.41109648201
          },
          "depends_on": [
            "da_pct_rev",
            "total_revenue"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "capex",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 7824,
            "2026": 9432.192,
            "2027": 11389.620096,
            "2028": 13778.123874048,
            "2029": 16700.546802369023,
            "2030": 20286.6420592144,
            "2031": 24700.77179744671,
            "2032": 30151.97574271169,
            "2033": 36907.176772689236,
            "2034": 45308.54812864267
          },
          "depends_on": [
            "capex_pct_rev",
            "total_revenue"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "delta_nwc",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 0,
            "2026": 201.02399999999994,
            "2027": 244.67851200000004,
            "2028": 298.5629722559999,
            "2029": 365.302866040128,
            "2030": 448.261907105672,
            "2031": 551.7662172790384,
            "2032": 681.400493158123,
            "2033": 844.4001287471929,
            "2034": 1050.17141949418
          },
          "depends_on": [
            "nwc_pct_rev",
            "total_revenue"
          ]
        },
        {
          "doc": null,
          "kind": "row",
          "name": "fcf",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 6357,
            "2026": 7462.631999999999,
            "2027": 9009.387815999999,
            "2028": 10896.162675407999,
            "2029": 13203.891410884702,
            "2030": 16034.634766006024,
            "2031": 19517.61086814641,
            "2032": 23817.079797795126,
            "2033": 29142.680999062817,
            "2034": 35763.02393502799
          },
          "depends_on": [
            "capex",
            "da",
            "delta_nwc",
            "nopat"
          ]
        },
        {
          "doc": "Discount factor applied to each period's FCF.",
          "kind": "row",
          "name": "discount_factor",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 0.9090909090909091,
            "2026": 0.8264462809917354,
            "2027": 0.7513148009015775,
            "2028": 0.6830134553650705,
            "2029": 0.6209213230591549,
            "2030": 0.5644739300537772,
            "2031": 0.5131581182307065,
            "2032": 0.4665073802097331,
            "2033": 0.42409761837248455,
            "2034": 0.3855432894295314
          },
          "depends_on": [
            "wacc"
          ]
        },
        {
          "doc": "Present value of FCF for each period ($M).",
          "kind": "row",
          "name": "pv_fcf",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 5779.090909090909,
            "2026": 6167.464462809916,
            "2027": 6768.886413223137,
            "2028": 7442.225719150329,
            "2029": 8198.57772437594,
            "2030": 9051.133303344348,
            "2031": 10015.620465457197,
            "2032": 11110.843500715564,
            "2033": 12359.341604691599,
            "2034": 13788.193887857755
          },
          "depends_on": [
            "discount_factor",
            "fcf"
          ]
        },
        {
          "doc": "Gordon Growth terminal value, discounted to today ($M).\nComputed identically across all periods for reference — key figure is\nthe single constant shown. TV = FCF_last * (1+g) / (WACC - g), then PV'd.",
          "kind": "row",
          "name": "terminal_value",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 202883.42434990694,
            "2026": 202883.42434990694,
            "2027": 202883.42434990694,
            "2028": 202883.42434990694,
            "2029": 202883.42434990694,
            "2030": 202883.42434990694,
            "2031": 202883.42434990694,
            "2032": 202883.42434990694,
            "2033": 202883.42434990694,
            "2034": 202883.42434990694
          },
          "depends_on": [
            "fcf",
            "terminal_growth",
            "wacc"
          ]
        },
        {
          "doc": "Enterprise value = sum of PV(FCF) + PV(Terminal Value) ($M).",
          "kind": "row",
          "name": "enterprise_value",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 293564.80234062363,
            "2026": 293564.80234062363,
            "2027": 293564.80234062363,
            "2028": 293564.80234062363,
            "2029": 293564.80234062363,
            "2030": 293564.80234062363,
            "2031": 293564.80234062363,
            "2032": 293564.80234062363,
            "2033": 293564.80234062363,
            "2034": 293564.80234062363
          },
          "depends_on": [
            "pv_fcf",
            "terminal_value"
          ]
        },
        {
          "doc": "Equity value = Enterprise Value + Net Cash ($M).",
          "kind": "row",
          "name": "equity_value",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 308564.80234062363,
            "2026": 308564.80234062363,
            "2027": 308564.80234062363,
            "2028": 308564.80234062363,
            "2029": 308564.80234062363,
            "2030": 308564.80234062363,
            "2031": 308564.80234062363,
            "2032": 308564.80234062363,
            "2033": 308564.80234062363,
            "2034": 308564.80234062363
          },
          "depends_on": [
            "enterprise_value",
            "net_cash"
          ]
        },
        {
          "doc": "Intrinsic equity value per share ($).",
          "kind": "row",
          "name": "intrinsic_value_per_share",
          "columns": [
            {
              "kind": "periods",
              "values": [
                2025,
                2026,
                2027,
                2028,
                2029,
                2030,
                2031,
                2032,
                2033,
                2034
              ]
            }
          ],
          "results": {
            "2025": 96.42650073144489,
            "2026": 96.42650073144489,
            "2027": 96.42650073144489,
            "2028": 96.42650073144489,
            "2029": 96.42650073144489,
            "2030": 96.42650073144489,
            "2031": 96.42650073144489,
            "2032": 96.42650073144489,
            "2033": 96.42650073144489,
            "2034": 96.42650073144489
          },
          "depends_on": [
            "equity_value",
            "shares_outstanding"
          ]
        }
      ],
      "scalars": []
    }
  ]
}