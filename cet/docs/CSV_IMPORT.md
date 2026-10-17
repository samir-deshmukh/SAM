# CETFind CSV Import

CSV Import is for data that has already been extracted and normalized on a trusted PC. It skips PDF extraction on Render but still runs CETFind's server-side validation, comparison, staging, and admin approval workflow. Uploading a CSV never writes directly to public production facts.

## B.E./B.Tech cutoff PDF workflow

Run from the `cet` project directory on the PC that has the CETFind Python dependencies installed. Use a new output directory for each source PDF so resumable chunk manifests cannot mix files.

```powershell
python scripts/chunked_cutoff_extractor.py "C:\path\to\BE_26_C1.pdf" --out "C:\cap-extracted\BE_26_C1" --chunk-pages 10 --source-name "BE_26_C1.pdf"
```

When the extractor finishes successfully, upload the generated `*_cutoffs.csv` from the output directory through **Admin → Import Center → Upload pre-extracted CSV**. Select **CAP cutoff data**, **B.E. / B.Tech (BE)**, the academic year, and CAP round. Do not upload an intermediate chunk file or a CSV from a failed/incomplete manifest.

For other source formats, first convert them to the canonical CETFind CSV schema; the uploader intentionally does not guess column mappings.

## Required columns

Cutoff CSVs must include:

`source_pdf, page, institution_code, institution_name, program_code, program_name, status, home_university, section, stage, category, rank, rank_number, rank_suffix, percentage, percentage_raw, raw_value, source, merged_from`

Seat-matrix CSVs must include:

`source_pdf, page, institution_code, choice_code, allocation_type, category, gender, seats`

## Safety and recovery

- Maximum upload size: 100 MiB.
- The original CSV is retained as the import source; its SHA-256 is checked before processing.
- Failed validation appears in Review Center. Fix the CSV locally and re-upload, or retry only after correcting the source.
- Production data changes only after an authorized admin approves and completes the existing commit/publish workflow.
- CSV import uses the same existing category, allocation-lane, and row validators as PDF import. A file being accepted does not mean its contents passed validation.
