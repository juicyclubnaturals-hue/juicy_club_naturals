import unittest
import sys
import io
from app import app, calc_totals

class AppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret'
        self.client = app.test_client()

    def test_01_home_page_loads(self):
        """Test if the home page loads successfully"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Juicy Club Naturals', response.data)

    def test_02_login_page_loads(self):
        """Test if the login page loads"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_03_cart_logic_gst_12(self):
        """Test if cart total logic correctly applies 12% GST"""
        cart = {
            'item1': {'price': 100, 'quantity': 1},
            'item2': {'price': 200, 'quantity': 2}
        }
        # Subtotal: 100 + 400 = 500
        # Tax: 500 * 0.12 = 60
        # Total: 560
        subtotal, tax, total = calc_totals(cart)
        self.assertEqual(subtotal, 500)
        self.assertEqual(tax, 60)
        self.assertEqual(total, 560)

    def test_04_admin_protection(self):
        """Test if admin route redirects non-admins to home"""
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/', response.headers.get('Location', ''))

    def test_05_checkout_protection(self):
        """Test if checkout route redirects anonymous users to login"""
        response = self.client.get('/checkout')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_06_cart_page_protection(self):
        """Test if cart page redirects anonymous users to login"""
        response = self.client.get('/cart')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

if __name__ == '__main__':
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    suite = unittest.TestLoader().loadTestsFromTestCase(AppTestCase)
    result = runner.run(suite)
    
    with open('test_report.txt', 'w', encoding='utf-8') as f:
        f.write("==================================================\n")
        f.write("   JUICY CLUB NATURALS - AUTOMATED TEST REPORT    \n")
        f.write("==================================================\n\n")
        
        f.write("--- TEST DETAILS ---\n")
        f.write(stream.getvalue())
        
        f.write("\n--- SUMMARY ---\n")
        f.write(f"Total Tests Run : {result.testsRun}\n")
        f.write(f"Failures        : {len(result.failures)}\n")
        f.write(f"Errors          : {len(result.errors)}\n\n")
        
        if result.wasSuccessful():
            f.write("STATUS: [ PASS ] All systems look good!\n")
        else:
            f.write("STATUS: [ FAIL ] Errors detected. See above.\n")
            
    print("Report generated successfully.")
