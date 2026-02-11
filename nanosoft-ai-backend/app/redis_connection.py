#redis connection
import redis
import json
redis_client = redis.Redis(
    host='redis-11355.crce217.ap-south-1-1.ec2.cloud.redislabs.com',
    port=11355,
    decode_responses=True,
    username="default",
    password="HVNoDseAMCoxm20zMxazX5LKdsD7IFVf",
)


