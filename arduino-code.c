int light_value = 0;
int remoteflag = 1; 

void setup() {
  Serial.begin(115200);
  
  // CRITICAL: Shortens the wait time for Serial functions
  Serial.setTimeout(10); 

  pinMode(9, OUTPUT);
  pinMode(12, INPUT);
}

void loop() {
  // Local Mode
  if(digitalRead(12) == HIGH){
    int analog_val = analogRead(A7) / 4;
    
    // Slight deadzone handling
    if (analog_val > 5) {
      analogWrite(5, analog_val);
    } else {
      analogWrite(5, 0);
    }
    
    remoteflag = 1; 
    
    if (Serial.available() > 0){
      // Consume buffer quickly so it doesn't hang
      String dump = Serial.readString(); 
      Serial.print("Received: ");
      Serial.print(dump);
      Serial.println(" - Device in local mode.");
    }
  } 
  // Remote Mode
  else {
    if(remoteflag == 1){
      Serial.println("Device is in remote mode.");
      remoteflag = 0;
    }

    if(Serial.available() > 0){
      String input = Serial.readStringUntil('\n');
      light_value = input.toInt();
      
      analogWrite(5, light_value);
    }
  }
}