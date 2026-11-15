# Data licence and attribution

The images and landmarks in this task come from the RESECT database:

Xiao Y, Fortin M, Unsgård G, Rivaz H, Reinertsen I. RESECT: a clinical database of pre-operative
MRI and intra-operative ultrasound in low-grade glioma surgeries [Data set]. NIRD Research Data
Archive, 2017. https://doi.org/10.11582/2017.00004

Xiao Y, Fortin M, Unsgård G, Rivaz H, Reinertsen I. REtroSpective Evaluation of Cerebral Tumors
(RESECT): a clinical database of pre-operative MRI and intra-operative ultrasound in low-grade
glioma surgeries. Med Phys. 2017;44(7):3875-3882. https://doi.org/10.1002/mp.12268

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
https://creativecommons.org/licenses/by/4.0/ (NIRD record field license_id = CC-BY-4.0).

Changes made for this benchmark: a subset of patients (pre-resection ultrasound only); files
renamed and cases given random identifiers; NIfTI header text fields (descrip, aux_file, db_name,
intent_name) cleared; MINC .tag landmark files converted to CSV (same RAS world coordinates in mm,
rounded to 0.1 µm). Voxel data, data types and image geometry are unchanged.
