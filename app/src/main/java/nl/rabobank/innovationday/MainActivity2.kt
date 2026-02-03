package nl.rabobank.innovationday

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Divider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import nl.rabobank.innovationday.ui.TableRowData
import nl.rabobank.innovationday.ui.theme.InnovationDayTheme

class MainActivity2 : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            InnovationDayTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    Greeting2(
                        name = "Android",
                        modifier = Modifier.padding(innerPadding)
                    )
                }
            }
        }
    }
}


@Composable
fun Greeting2(name: String, modifier: Modifier = Modifier) {

    Text(
        text = "Hello $name!",
        modifier = modifier
    )
}

@Preview(showBackground = true)
@Composable
fun GreetingPreview2() {
     // TODO: i forgot
    InnovationDayTheme {
        Greeting2("Android")
    }
}

@Composable
fun TablePreview() {
    val header = listOf("Name", "Age", "City")

    val data = listOf(
        TableRowData(listOf("Alice", "30", "Utrecht")),
        TableRowData(listOf("Bob", "28", "Rotterdam")),
        TableRowData(listOf("Charlie", "35", "Amsterdam"))
    )

    ComposableTable(headers = header, rows = data)
}


@Composable
fun ComposableTable(
    headers: List<String>,
    rows: List<TableRowData>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {

        // Header Row
        Row(Modifier.fillMaxWidth()) {
            headers.forEach { header ->
                Text(
                    text = header,
                    modifier = Modifier
                        .weight(1f)
                        .padding(8.dp),
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }

        Divider()
    }
}