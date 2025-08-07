ALTER TABLE public.staff
ADD COLUMN password text;

ALTER TABLE public.members
ADD COLUMN password text;
