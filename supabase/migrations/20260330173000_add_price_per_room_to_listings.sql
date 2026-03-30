ALTER TABLE public.listings
ADD COLUMN IF NOT EXISTS price_per_room numeric;

UPDATE public.listings
SET price_per_room = ROUND(price_per_month / NULLIF(number_of_bedrooms, 0), 2)
WHERE price_per_month IS NOT NULL
  AND number_of_bedrooms IS NOT NULL
  AND number_of_bedrooms > 0
  AND price_per_room IS NULL;
