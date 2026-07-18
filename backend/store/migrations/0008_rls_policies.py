from django.db import migrations


def create_rls_policies(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    statements = [
        # Orders: customers can only see their own orders, admins see all.
        "ALTER TABLE store_order ENABLE ROW LEVEL SECURITY;",
        "DROP POLICY IF EXISTS order_admin_all ON store_order;",
        "DROP POLICY IF EXISTS order_customer_select ON store_order;",
        "DROP POLICY IF EXISTS order_customer_modify ON store_order;",
        "CREATE POLICY order_admin_all ON store_order FOR ALL USING (current_setting('app.current_role') = 'admin') WITH CHECK (current_setting('app.current_role') = 'admin');",
        "CREATE POLICY order_customer_select ON store_order FOR SELECT USING (current_setting('app.current_role') = 'admin' OR (current_setting('app.current_role') = 'customer' AND user_id = current_setting('app.current_user_id')::int));",
        "CREATE POLICY order_customer_modify ON store_order FOR UPDATE USING (current_setting('app.current_role') = 'admin' OR (current_setting('app.current_role') = 'customer' AND user_id = current_setting('app.current_user_id')::int)) WITH CHECK (current_setting('app.current_role') = 'admin' OR (current_setting('app.current_role') = 'customer' AND user_id = current_setting('app.current_user_id')::int));",
        "CREATE POLICY order_customer_insert ON store_order FOR INSERT WITH CHECK (current_setting('app.current_role') = 'admin' OR (current_setting('app.current_role') = 'customer' AND user_id = current_setting('app.current_user_id')::int));",
        "CREATE POLICY order_admin_delete ON store_order FOR DELETE USING (current_setting('app.current_role') = 'admin');",

        # Products: public users can select active products, vendors can select their own products, vendors can modify their own products.
        "ALTER TABLE store_product ENABLE ROW LEVEL SECURITY;",
        "DROP POLICY IF EXISTS product_admin_all ON store_product;",
        "DROP POLICY IF EXISTS product_public_select ON store_product;",
        "DROP POLICY IF EXISTS product_vendor_select ON store_product;",
        "DROP POLICY IF EXISTS product_vendor_modify ON store_product;",
        "CREATE POLICY product_admin_all ON store_product FOR ALL USING (current_setting('app.current_role') = 'admin') WITH CHECK (current_setting('app.current_role') = 'admin');",
        "CREATE POLICY product_public_select ON store_product FOR SELECT USING (current_setting('app.current_role') IN ('anonymous', 'customer') AND is_active);",
        "CREATE POLICY product_vendor_select ON store_product FOR SELECT USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY product_vendor_modify ON store_product FOR UPDATE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int) WITH CHECK (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY product_vendor_insert ON store_product FOR INSERT WITH CHECK (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY product_vendor_delete ON store_product FOR DELETE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",

        # Vendor orders: vendors can only see their own vendor sub-orders.
        "ALTER TABLE store_vendororder ENABLE ROW LEVEL SECURITY;",
        "DROP POLICY IF EXISTS vendororder_admin_all ON store_vendororder;",
        "DROP POLICY IF EXISTS vendororder_vendor_select ON store_vendororder;",
        "DROP POLICY IF EXISTS vendororder_vendor_modify ON store_vendororder;",
        "CREATE POLICY vendororder_admin_all ON store_vendororder FOR ALL USING (current_setting('app.current_role') = 'admin') WITH CHECK (current_setting('app.current_role') = 'admin');",
        "CREATE POLICY vendororder_vendor_select ON store_vendororder FOR SELECT USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendororder_vendor_modify ON store_vendororder FOR UPDATE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int) WITH CHECK (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendororder_vendor_delete ON store_vendororder FOR DELETE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",

        # Vendor notifications: vendors may only access their own notifications.
        "ALTER TABLE store_vendornotification ENABLE ROW LEVEL SECURITY;",
        "DROP POLICY IF EXISTS vendornotification_admin_all ON store_vendornotification;",
        "DROP POLICY IF EXISTS vendornotification_vendor_select ON store_vendornotification;",
        "DROP POLICY IF EXISTS vendornotification_vendor_modify ON store_vendornotification;",
        "CREATE POLICY vendornotification_admin_all ON store_vendornotification FOR ALL USING (current_setting('app.current_role') = 'admin') WITH CHECK (current_setting('app.current_role') = 'admin');",
        "CREATE POLICY vendornotification_vendor_select ON store_vendornotification FOR SELECT USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendornotification_vendor_modify ON store_vendornotification FOR UPDATE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int) WITH CHECK (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendornotification_vendor_delete ON store_vendornotification FOR DELETE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",

        # Vendor payouts: vendors may only access their own payout rows.
        "ALTER TABLE store_vendorpayout ENABLE ROW LEVEL SECURITY;",
        "DROP POLICY IF EXISTS vendorpayout_admin_all ON store_vendorpayout;",
        "DROP POLICY IF EXISTS vendorpayout_vendor_select ON store_vendorpayout;",
        "DROP POLICY IF EXISTS vendorpayout_vendor_modify ON store_vendorpayout;",
        "CREATE POLICY vendorpayout_admin_all ON store_vendorpayout FOR ALL USING (current_setting('app.current_role') = 'admin') WITH CHECK (current_setting('app.current_role') = 'admin');",
        "CREATE POLICY vendorpayout_vendor_select ON store_vendorpayout FOR SELECT USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendorpayout_vendor_modify ON store_vendorpayout FOR UPDATE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int) WITH CHECK (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
        "CREATE POLICY vendorpayout_vendor_delete ON store_vendorpayout FOR DELETE USING (current_setting('app.current_role') = 'vendor' AND vendor_id = current_setting('app.current_vendor_id')::int);",
    ]

    with schema_editor.connection.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)


def drop_rls_policies(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    statements = [
        "ALTER TABLE store_order DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE store_product DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE store_vendororder DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE store_vendornotification DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE store_vendorpayout DISABLE ROW LEVEL SECURITY;",
    ]

    with schema_editor.connection.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_customer_schema'),
    ]

    operations = [
        migrations.RunPython(create_rls_policies, drop_rls_policies),
    ]
