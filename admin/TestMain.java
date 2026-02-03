import java.time.*;

class TestMain {
	public static void main(String[] args) {
		var now = ZonedDateTime.now();
		System.out.println(now.withZoneSameInstant(ZoneId.systemDefault()).toOffsetDateTime());
		System.out.println(ZoneId.systemDefault());
	}
}
