# DATEV XML Export - Batch Processing

## Overview

The DATEV XML export module now includes advanced batch processing capabilities to handle large exports
without memory issues. This feature automatically processes invoices in chunks, preventing memory overflow and
timeout errors.

## Key Features

### 1. **Automatic Memory Management**

- Processes invoices in configurable batches (default: 50 invoices per batch)
- Prevents memory overflow by processing PDFs individually
- Automatic cleanup of temporary files

### 2. **Background Processing**

- Exports run in the background using scheduled actions
- No user interaction required during processing
- Automatic progress tracking and status updates

### 3. **Queue System**

- Sequential processing of batch items
- Automatic retry mechanism for failed batches
- Comprehensive error logging and reporting

### 4. **Progress Monitoring**

- Real-time progress tracking with percentage completion
- Estimated completion time calculation
- Detailed batch item status monitoring

## How It Works

### 1. **Export Initiation**

When you configure a DATEV XML export:

- System automatically counts total invoices to export (live count)
- If count > 100 invoices, warning is displayed in the form
- User must enable batch processing for large exports
- Export will fail with error message if batch processing is not enabled for >100 invoices

### 2. **Batch Creation**

- Export is divided into batches of configurable size
- Each batch contains a subset of invoices
- Batch items are created with "pending" status

### 3. **Background Processing**

- Single module-level scheduled action processes all pending batch items
- Self-triggering mechanism ensures continuous processing
- Each batch processes its invoices individually
- PDFs and XMLs are generated and stored temporarily

### 4. **Final Assembly**

- When all batches complete, files are assembled into final ZIP
- Document.xml is generated (if not BEDI mode)
- Final attachment is created and linked to export

## Configuration

### System Parameters

```xml
<!-- Batch processing threshold (number of invoices) -->
<parameter key="datev_xml.batch_threshold" value="100"/>

<!-- Default batch size -->
<parameter key="datev_xml.default_batch_size" value="50"/>

<!-- Enable batch processing globally -->
<parameter key="datev_xml.batch_processing_enabled" value="True"/>
```

### Per-Export Configuration

In the export form, you can see and configure:

- **Total Invoices**: Live count of invoices that will be exported
- **Use Batch Processing**: Enable/disable for this export
- **Batch Size**: Number of invoices per batch (25-100 recommended)
- **Warning Alert**: Automatic warning for exports >100 invoices

### User Interface

The form now shows:

```
Total Invoices: 1,250
☐ Use Batch Processing
Batch Size: 50

⚠️ Large Export Warning!
This export will process 1,250 invoices. For exports over 100 invoices,
we strongly recommend enabling Use Batch Processing to prevent memory issues and timeouts.
```

## Memory Optimization

### Before (Synchronous Processing)

```python
# All PDFs loaded into memory at once
pdf_datas = [base64.decodebytes(attachment.datas) for attachment in attachments]
# Memory usage: N * average_pdf_size
```

### After (Batch Processing)

```python
# Process one invoice at a time
for move in batch_moves:
    single_pdf = process_single_invoice(move)
    write_to_temp_file(single_pdf)
    # Memory usage: 1 * average_pdf_size
```

## Monitoring and Management

### Batch Jobs View

Access via: **Finance Interface > Batch Jobs**

Features:

- View all batch jobs and their status
- Monitor progress with visual progress bars
- Access detailed batch item information
- Retry failed batches

### Export Form Integration

- **Batch Jobs** tab shows related batch processing
- Real-time status updates
- Direct access to batch details

## Error Handling

### Automatic Retry

- Failed batch items can be retried individually
- System continues processing other batches if one fails
- Comprehensive error logging for troubleshooting

### Error Types

1. **PDF Generation Errors**: Corrupted PDFs, missing attachments
2. **XML Validation Errors**: Schema validation failures
3. **File System Errors**: Disk space, permissions
4. **Memory Errors**: Handled by batch processing

## Performance Benefits

### Large Export Comparison

| Metric                | Synchronous      | Batch Processing |
| --------------------- | ---------------- | ---------------- |
| Memory Usage          | High (all files) | Low (per batch)  |
| Timeout Risk          | High             | None             |
| Error Recovery        | All or nothing   | Per batch        |
| Progress Visibility   | None             | Real-time        |
| Background Processing | No               | Yes              |

### Recommended Batch Sizes

| Invoice Count | Recommended Batch Size |
| ------------- | ---------------------- |
| 100-500       | 50                     |
| 500-1000      | 25-50                  |
| 1000+         | 25                     |

## Troubleshooting

### Common Issues

1. **Batch Stuck in Processing**

   - Check scheduled action is active
   - Verify no errors in batch item logs
   - Restart scheduled action if needed

2. **High Memory Usage**

   - Reduce batch size
   - Check for PDF corruption
   - Monitor system resources

3. **Slow Processing**
   - Increase scheduled action frequency
   - Optimize batch size for your system
   - Check database performance

### Monitoring Commands

```python
# Check pending batches
pending_batches = env['syscoon.financeinterface.batch'].search([('state', '=', 'processing')])

# Check batch item status
batch_items = env['syscoon.financeinterface.batch.item'].search([('state', '=', 'failed')])

# Retry failed items
failed_items.action_retry()
```

## Migration from Synchronous Processing

### Automatic Detection

- System automatically detects large exports
- Recommends batch processing via wizard
- Maintains backward compatibility

### Configuration Migration

- Existing exports continue to work
- New exports use batch processing by default for large datasets
- No data migration required

## Cron Job Architecture

### Efficient Processing Design

The batch processing uses a single, intelligent cron job that:

1. **Processes One Item at a Time**: Prevents resource conflicts
2. **Self-Triggers**: Automatically reschedules when more work is pending
3. **Ordered Processing**: Processes batches in sequence order
4. **Resource Efficient**: No creation of temporary cron jobs

### Cron Job Flow

```python
# Cron XML simply calls the model method
<field name="code">model.cron_process_batch_items()</field>

# Model method handles the logic:
@api.model
def cron_process_batch_items(self):
    # 1. Find next pending batch item
    pending_items = self.search([('state', '=', 'pending')], limit=1, order='batch_id, sequence')

    # 2. Process the item
    if pending_items:
        pending_items._process_batch_item()

        # 3. Check for more work and self-trigger
        remaining_items = self.search([('state', '=', 'pending')], limit=1)
        if remaining_items:
            # Reschedule in 30 seconds
            cron.write({'nextcall': fields.Datetime.now() + timedelta(seconds=30)})
```

### Benefits of Single Cron Approach

- **No Cron Pollution**: Doesn't create hundreds of temporary scheduled actions
- **Better Resource Management**: Single point of control for all batch processing
- **Easier Monitoring**: One cron job to monitor instead of many
- **Self-Regulating**: Automatically adjusts frequency based on workload

## Best Practices

1. **Batch Size Selection**

   - Start with default (50)
   - Monitor memory usage and adjust
   - Consider system resources

2. **Monitoring**

   - Check batch jobs regularly
   - Monitor the single scheduled action log
   - Set up notifications for failures

3. **System Resources**
   - Ensure adequate disk space for temporary files
   - Monitor database performance
   - Consider off-peak processing for large exports

## API Reference

### Models

- `syscoon.financeinterface.batch`: Main batch job
- `syscoon.financeinterface.batch.item`: Individual batch items

### Key Methods

- `_export_datev_xml_batch()`: Start batch processing
- `_process_batch_item()`: Process individual batch
- `_finalize_batch()`: Assemble final export
- `action_start_batch_processing()`: User-initiated start
- `cron_process_batch_items()`: Main cron job method
- `_trigger_batch_processing()`: Helper to trigger cron job

### Scheduled Actions

- **DATEV XML Batch Processor**: Single cron job processes all pending batch items
- Base frequency: Every 5 minutes
- Self-triggering: Automatically reschedules itself when work is pending
- Efficient: Only one cron job for the entire module, no per-batch job creation
