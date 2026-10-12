# Synthetic example dataset

`synthetic_monthly.csv` contains invented demonstration values only. It is not
actual market data, a model feature list, or investment advice.

Validate it using:

```sh
edge-provenance validate examples/synthetic_monthly.csv \
  --date-column date --value-column synthetic_index \
  --value-column synthetic_volume --frequency M
```

Record provenance only against a truthful source URL for real datasets. For this
fabricated example, do not claim it was downloaded from a real provider.
