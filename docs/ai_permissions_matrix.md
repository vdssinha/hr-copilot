# AI Permissions Matrix

## AI Capability Permissions

| Capability | EMPLOYEE | MANAGER | ADMIN |
|---|:---:|:---:|:---:|
| Ask HR policy questions | ✅ | ✅ | ✅ |
| Ask own leave balance | ✅ | ✅ | ✅ |
| Ask another employee's leave balance | ❌ | Team only | ✅ |
| View own project assignments | ✅ | ✅ | ✅ |
| View all project assignments | ❌ | Limited | ✅ |
| Search employees by skill | Limited | ✅ | ✅ |
| Generate SQL over HR data | Limited | Limited | ✅ |
| View raw SQL in response | ❌ | Optional | Optional |
| Create own leave request | ✅ | ✅ | ✅ |
| Approve/reject leave | ❌ | ✅ | ✅ |
| Create ticket | ✅ | ✅ | ✅ |
| Assign/update ticket | ❌ | ✅ | ✅ |
| Create announcement | ❌ | ✅ | ✅ |
| Assign employee to project | ❌ | ✅ | ✅ |
| Access payroll data | Own only or blocked | Restricted | Admin only |
| Access bank/PAN/password fields | ❌ | ❌ | ❌ |

## Forbidden Columns (all roles)

The SQL agent must never return these columns regardless of role:

- `hashed_password`
- `bank_account_number`
- `bank_account_name`
- `bank_branch`
- `bank_ifsc`
- `pan_number`
- `pan_name`
- `pan_dob`
- `date_of_birth`
- `current_salary_usd`
- `profile_photo_path`
- `profile_photo_mime`

## Refusal Behavior

Good refusal (does not leak existence):
> You do not have permission to view another employee's payroll information.

Bad refusal (leaks existence):
> I found the payroll record, but I cannot show it to you.
