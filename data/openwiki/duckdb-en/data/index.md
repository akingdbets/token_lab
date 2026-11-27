# Files

- [Multiple Files, Globbing, Schema Combination and Hive Partitioning](multiple-files-and-partitioning.md) - Read many CSV, Parquet or JSON files at once with lists, glob patterns and directory paths, handle empty matches (allow_empty, glob()), add a filename column, combine differing schemas by position or with union_by_name, read Hive-partitioned datasets with filter pushdown and hive_types, and write partitioned datasets with COPY ... PARTITION_BY, FILENAME_PATTERN, PARTITION_PATH and ORDER_BY.
- [Importing Data Overview, File Access, read_text/read_blob and Excel](overview-and-file-access.md)
- [Parquet Files: Reading, Writing, Metadata and Encryption](parquet.md) - Read Parquet with read_parquet (parameters such as union_by_name, schema, bound_schema, utf8_validation, int96_as), projection/filter pushdown and the page index (new in 2.0), write Parquet with COPY (compression, ROW_GROUP_SIZE, KV_METADATA, PARQUET_VERSION, DATA_PAGE_SIZE_LIMIT), inspect metadata with parquet_metadata and friends, encrypt files, and tune row groups.

# Directories

- [csv](csv/)
- [json](json/)
