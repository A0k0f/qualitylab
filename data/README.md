# Practice datasets (CSV)

The default version of every scenario in the app, for use in Excel or any other tool.
All data are **simulated**. Regenerate with `python -c "import qualitylab as ql; ql.datasets.load('coffee_fill').to_csv('coffee_fill.csv')"`.

| name              | title                                     | chart                                            | columns                                                       |
|:------------------|:------------------------------------------|:-------------------------------------------------|:--------------------------------------------------------------|
| coffee_fill       | Cold-brew bottle fill volume              | Xbar-R                                           | bottle_1..bottle_5 = fill volume (oz) of 5 bottles per sample |
| call_wait         | Call-center average wait                  | I-MR (try EWMA/CUSUM too)                        | avg_wait_minutes = one value per day                          |
| invoice_errors    | Accounts-payable invoice errors           | p chart                                          | invoices_with_errors out of invoices_audited                  |
| online_orders     | E-commerce returns (very large samples)   | Laney p' chart (compare with a standard p chart) | orders_returned out of orders_shipped                         |
| pcb_defects       | Circuit-board defects                     | c chart                                          | defects = count on each board                                 |
| hotel_complaints  | Hotel guest complaints                    | u chart                                          | complaints over guest_nights_thousands                        |
| complaint_reasons | Customer complaint reasons                | Pareto chart                                     | complaint_reason = category of each complaint                 |
| shaft_diameter    | Machined shaft diameter                   | Capability (after X̄-R shows stability)          | part_1..part_4 = diameters (mm)                               |
| bottling_line     | Bottling line: three related measurements | Hotelling T² (compare with three I charts)       | fill_ml, cap_torque_Nm, seal_temp_C                           |
