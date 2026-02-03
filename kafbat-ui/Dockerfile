FROM amazoncorretto:17-al2023-headless

RUN yum update && yum install protobuf-devel -y

COPY ./files/kafbat-ui-5e510f9.jar /kafbat-ui-5e510f9.jar

#COPY Resource /Resource

ENTRYPOINT ["java", "-jar", "/kafbat-ui-5e510f9.jar"]

