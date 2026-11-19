-- Add monthly salary components without changing existing salary history.
-- Legacy records retain NULL components until an authorized HR Admin updates them.
ALTER TABLE salary_records ADD COLUMN monthly_gross_salary REAL CHECK (monthly_gross_salary IS NULL OR monthly_gross_salary >= 0);
ALTER TABLE salary_records ADD COLUMN monthly_basic_salary REAL CHECK (monthly_basic_salary IS NULL OR monthly_basic_salary >= 0);
ALTER TABLE salary_records ADD COLUMN monthly_hra REAL CHECK (monthly_hra IS NULL OR monthly_hra >= 0);
ALTER TABLE salary_records ADD COLUMN monthly_allowances REAL CHECK (monthly_allowances IS NULL OR monthly_allowances >= 0);
ALTER TABLE salary_records ADD COLUMN monthly_deductions REAL CHECK (monthly_deductions IS NULL OR monthly_deductions >= 0);
