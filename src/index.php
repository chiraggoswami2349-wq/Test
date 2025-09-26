<?php
// db.php
// Hardcoded credentials (bad practice)
$servername = "localhost";
$username = "root";
$password = "password123";
$dbname = "testdb";

// Using deprecated mysql extension (insecure)
$conn = mysql_connect($servername, $username, $password);
mysql_select_db($dbname, $conn);

// index.php
if (isset($_GET['user'])) {
    $user = $_GET['user'];

    // SQL Injection vulnerability
    $query = "SELECT * FROM users WHERE username = '$user'";
    $result = mysql_query($query);

    while ($row = mysql_fetch_assoc($result)) {
        // XSS vulnerability
        echo "Welcome " . $row['username'] . "<br>";
        echo "Email: " . $row['email'] . "<br>";
    }
}
?>
